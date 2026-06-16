"""The per-user profile: persistence and how it reaches the assembled brain."""

import pytest

from pennyworth import NULL_PACK, NULL_PROFILE, Profile, build_system_prompt
from pennyworth import profile as prof


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    """Every test gets its own PENNYWORTH_HOME — never the developer's real one."""
    monkeypatch.setenv("PENNYWORTH_HOME", str(tmp_path))


# --- persistence ---


def test_load_is_null_when_unset():
    assert prof.load_profile() == NULL_PROFILE
    assert not NULL_PROFILE.is_set


def test_save_and_load_round_trip():
    saved = prof.save_profile(Profile(name="Haim", address="sir"))
    assert saved == Profile(name="Haim", address="sir")
    assert prof.load_profile() == Profile(name="Haim", address="sir")
    assert prof.load_profile().is_set


def test_update_merges_fields_independently():
    prof.save_profile(Profile(name="Haim", address="sir"))
    prof.update_profile(address="madam")  # name left untouched
    assert prof.load_profile() == Profile(name="Haim", address="madam")
    prof.update_profile(name="Dana")  # address left untouched
    assert prof.load_profile() == Profile(name="Dana", address="madam")


def test_address_is_validated_on_save():
    with pytest.raises(ValueError):
        prof.save_profile(Profile(name="x", address="captain"))


def test_address_is_normalized_to_lowercase():
    assert prof.save_profile(Profile(name="x", address="SIR")).address == "sir"


def test_out_of_range_address_on_disk_degrades_gracefully():
    prof.profile_path().write_text('name = "x"\naddress = "captain"\n')
    assert prof.load_profile() == Profile(name="x", address="")


def test_name_with_quotes_round_trips():
    prof.save_profile(Profile(name='Da"ve', address="sir"))
    assert prof.load_profile().name == 'Da"ve'


def test_clear_removes_the_profile():
    prof.save_profile(Profile(name="Haim", address="sir"))
    prof.clear_profile()
    assert prof.load_profile() == NULL_PROFILE
    assert not prof.profile_path().exists()


# --- reaching the brain ---


def test_null_profile_adds_no_user_block():
    assert "## Your User" not in build_system_prompt(NULL_PACK)


def test_profile_renders_name_and_address_into_brain():
    brain = build_system_prompt(NULL_PACK, profile=Profile(name="Haim", address="sir"))
    assert "## Your User" in brain
    assert "Haim" in brain
    assert "**sir**" in brain


def test_profile_with_name_only_asks_for_address():
    brain = build_system_prompt(NULL_PACK, profile=Profile(name="Haim"))
    assert "Haim" in brain
    assert "ask once" in brain


def test_profile_with_address_only_renders_honorific():
    brain = build_system_prompt(NULL_PACK, profile=Profile(address="madam"))
    assert "## Your User" in brain
    assert "**madam**" in brain
