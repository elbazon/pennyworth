"""Voice-to-text for Pennyworth.app — record, then transcribe.

Two earlier designs streamed live partials through an AVAudioEngine tap;
both crashed the app in live use. The tap block runs on a REALTIME audio
thread, and calling into Python there (GIL acquisition, pyobjc bridging)
is exactly the kind of thing CoreAudio kills processes over. So: no taps,
no Python on audio threads.

This design records with AVAudioRecorder (pure native, zero callbacks)
and, when the user stops, runs SFSpeechURLRecognitionRequest over the
file. No live partials — the transcript lands ~1-2s after stopping —
but nothing here can take the app down.

States via ``on_state``: 'recording' → 'transcribing' → 'done' (with
``on_text(final)``) or an error message. Permissions prompt on first use;
denial degrades to a message.
"""

from __future__ import annotations

import logging
import tempfile
import threading
from pathlib import Path

log = logging.getLogger(__name__)


class Dictation:
    """Record-then-transcribe; one session at a time."""

    def __init__(self):
        self._lock = threading.Lock()
        self._recorder = None
        self._path: Path | None = None
        self._on_text = None
        self._on_state = None

    @property
    def active(self) -> bool:
        return self._recorder is not None

    @staticmethod
    def _authorize_on_main(request_fn, timeout: float = 60.0) -> None:
        """Run an async TCC authorization request ON THE MAIN THREAD, then
        block this (worker) thread until it resolves.

        pywebview runs js_api calls — and therefore ``Dictation.start`` — on a
        worker thread (its own docs: "executed in a separate thread to prevent
        blocking the UI thread"). macOS will NOT present a privacy prompt for a
        request that originates off the main thread: the completion handler
        fires instantly with the *undetermined* status and no dialog appears —
        which surfaced to the user as "voice could not start". Marshalling the
        request onto the main thread via ``AppHelper.callAfter`` lets the
        prompt show; we wait here (not on main) so the main run loop stays free
        to present it. The callback accepts any args so it serves both the
        Speech handler (status) and the AVCaptureDevice handler (BOOL granted).
        """
        done = threading.Event()

        def _go():
            try:
                request_fn(lambda *_: done.set())
            except Exception:
                log.debug("auth request raised", exc_info=True)
                done.set()

        try:
            from PyObjCTools import AppHelper

            AppHelper.callAfter(_go)
        except Exception:
            _go()  # no AppHelper — try inline (may not present UI, but no worse)
        done.wait(timeout)

    def start(self, on_text, on_state) -> bool:
        with self._lock:
            if self._recorder is not None:
                return False
            try:
                import AVFoundation
                import Speech
                from Foundation import NSURL
            except ImportError as e:
                on_state(f"voice unavailable: {e}")
                return False

            # Permissions, requested on the MAIN THREAD (see _authorize_on_main)
            # so the prompt can actually appear. Speech first (transcription
            # needs it), then microphone (recording needs it) — fail before
            # recording, not after, with an actionable message either way.
            sstat = Speech.SFSpeechRecognizer.authorizationStatus()
            if sstat == Speech.SFSpeechRecognizerAuthorizationStatusNotDetermined:
                self._authorize_on_main(Speech.SFSpeechRecognizer.requestAuthorization_)
                sstat = Speech.SFSpeechRecognizer.authorizationStatus()
            if sstat != Speech.SFSpeechRecognizerAuthorizationStatusAuthorized:
                on_state(
                    "speech permission needed — enable Speech Recognition in "
                    "System Settings → Privacy & Security, then try again"
                )
                return False

            audio_type = AVFoundation.AVMediaTypeAudio
            mstat = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
                audio_type
            )
            if mstat == AVFoundation.AVAuthorizationStatusNotDetermined:
                self._authorize_on_main(
                    lambda cb: AVFoundation.AVCaptureDevice.requestAccessForMediaType_completionHandler_(
                        audio_type, cb
                    )
                )
                mstat = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
                    audio_type
                )
            if mstat != AVFoundation.AVAuthorizationStatusAuthorized:
                on_state(
                    "microphone permission needed — enable Microphone in "
                    "System Settings → Privacy & Security, then try again"
                )
                return False

            try:
                self._path = Path(tempfile.mkstemp(suffix=".m4a")[1])
                url = NSURL.fileURLWithPath_(str(self._path))
                settings = {
                    AVFoundation.AVFormatIDKey: 1633772320,  # kAudioFormatMPEG4AAC
                    AVFoundation.AVSampleRateKey: 44100.0,
                    AVFoundation.AVNumberOfChannelsKey: 1,
                }
                recorder, err = (
                    AVFoundation.AVAudioRecorder.alloc().initWithURL_settings_error_(url, settings, None)
                )
                if recorder is None or not recorder.record():
                    on_state(f"microphone failed{f': {err}' if err else ''}")
                    self._cleanup()
                    return False
            except Exception as e:
                log.debug("recording start failed", exc_info=True)
                on_state(f"voice failed: {type(e).__name__}")
                self._cleanup()
                return False

            self._recorder = recorder
            self._on_text, self._on_state = on_text, on_state
            on_state("recording")
            # Watchdog — never record forever.
            threading.Timer(120.0, self._watchdog).start()
            return True

    def _watchdog(self):
        if self._recorder is not None:
            self.stop()

    def stop(self, on_state=None) -> None:
        """Finish recording, transcribe the file on a worker thread."""
        with self._lock:
            recorder = self._recorder
            self._recorder = None
            if recorder is None:
                return
            on_text = self._on_text
            state = on_state or self._on_state or (lambda s: None)
            path = self._path
            try:
                recorder.stop()
            except Exception:
                log.debug("recorder stop noise", exc_info=True)

        state("transcribing")
        threading.Thread(
            target=self._transcribe, args=(path, on_text, state), daemon=True
        ).start()

    def _transcribe(self, path, on_text, on_state) -> None:
        try:
            import Speech
            from Foundation import NSURL

            recognizer = Speech.SFSpeechRecognizer.alloc().init()
            if recognizer is None or not recognizer.isAvailable():
                on_state("speech recognition unavailable")
                return
            request = Speech.SFSpeechURLRecognitionRequest.alloc().initWithURL_(
                NSURL.fileURLWithPath_(str(path))
            )
            done = threading.Event()
            outcome = {"text": "", "error": None}

            def handler(result, error):
                if result is not None and result.isFinal():
                    outcome["text"] = str(result.bestTranscription().formattedString())
                    done.set()
                elif error is not None:
                    outcome["error"] = str(error.localizedDescription())
                    done.set()

            recognizer.recognitionTaskWithRequest_resultHandler_(request, handler)
            if not done.wait(timeout=60):
                on_state("transcription timed out")
                return
            if outcome["error"] and not outcome["text"]:
                on_state(f"transcription failed: {outcome['error'][:120]}")
                return
            if outcome["text"]:
                on_text(outcome["text"])
            on_state("done")
        except Exception as e:
            log.debug("transcription failed", exc_info=True)
            on_state(f"voice failed: {type(e).__name__}")
        finally:
            self._cleanup()

    def _cleanup(self):
        try:
            if self._path and self._path.exists():
                self._path.unlink()
        except OSError:
            pass
        self._path = None
