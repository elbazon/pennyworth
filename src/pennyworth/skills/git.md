---
name: git
description: Use before advising on git workflows, branch strategies, conflict resolution, history rewriting, or any non-trivial git operation — covers the safe patterns and the landmines. NOT for casual one-liner git questions answered from common knowledge.
---

# Git — workflows, branch strategies, and safe history operations

## Branch strategy

Choose a model that fits the team's release cadence:

- **Trunk-based development** (recommended for fast iteration): everyone commits to `main` (or short-lived feature branches <2 days). Feature flags gate incomplete work. Requires strong CI — broken `main` is immediately everyone's problem.
- **GitFlow** (suits scheduled releases): `main` = stable, `develop` = integration, `feature/*`, `release/*`, `hotfix/*`. Overhead is real; worth it only when multiple release lines coexist.
- **GitHub Flow** (trunk-based + PR gate): branches off `main`, PR required, squash-merge or merge-commit, deploy from `main`. Simple and effective for most teams.

## Commit discipline

- **Subject line:** imperative mood, ≤72 chars, no trailing period. "Add retry logic" not "Added retry logic" or "This adds retry logic".
- **Body:** *why* not *what* — the diff already shows what. One blank line separates subject from body.
- **Atomic commits:** each commit leaves the repo in a buildable, testable state. Bisect only works when history is honest.
- **Never amend a pushed commit** unless the branch is explicitly understood to be force-pushable (e.g. your own feature branch, clearly communicated). Amending rewrites the commit hash; anyone who has already pulled sees a diverged history.

## Rewriting history safely

Before any destructive operation, confirm the commit is **not reachable from a remote ref** (`git branch -r --contains <sha>`).

| Operation | Safe when | Command |
|---|---|---|
| Amend last commit | Not yet pushed | `git commit --amend` |
| Interactive rebase | Branch not shared | `git rebase -i HEAD~N` |
| Squash on merge | Always — GitHub/GitLab do it server-side | PR setting |
| Force-push | Solo branch, team aware | `git push --force-with-lease` (safer than `--force`) |

**`--force-with-lease`** fails if the remote has commits you haven't fetched — it's the force-push that respects others. Always prefer it over bare `--force`.

## Conflict resolution

```bash
git merge feature-branch   # or git rebase main
# ... conflicts ...
git status                 # lists conflicted files
# edit files, removing <<<<<<<  =======  >>>>>>> markers
git add <resolved-files>
git merge --continue       # or git rebase --continue
```

For complex conflicts, a three-way merge tool helps:
```bash
git mergetool              # uses $GIT_MERGETOOL or git config merge.tool
```

When rebasing, resolve conflicts **one commit at a time** — the conflict is scoped to what that individual commit changed, which is usually smaller than a merge conflict.

## Keeping branches fresh

```bash
# Update main and rebase your feature branch on top of it
git fetch origin
git rebase origin/main     # from your feature branch
# Or, if the team uses merge-commits:
git merge origin/main
```

Prefer `rebase` for feature branches (keeps history linear); use `merge` for long-lived integration branches (preserves topology).

## Useful diagnostics

```bash
git log --oneline --graph --all   # visual branch topology
git log --stat                    # what changed in each commit
git bisect start HEAD <known-good-sha>   # binary-search a regression
git blame -L 40,60 path/to/file   # who touched these lines and when
git reflog                        # recover "lost" commits after reset/amend
git stash list                    # check for forgotten stashes
```

## Tag a release

```bash
git tag -a v1.2.3 -m "Release v1.2.3"
git push origin v1.2.3
```

Annotated tags (`-a`) carry a tagger, date, and message — prefer them over lightweight tags for releases. Delete a remote tag: `git push origin --delete v1.2.3`.

## Recovering from mistakes

| Mistake | Recovery |
|---|---|
| Committed to wrong branch | `git cherry-pick <sha>` onto the right branch, then `git revert <sha>` or `git reset HEAD~1` on the wrong one |
| Accidentally deleted a branch | `git reflog` to find the SHA, `git checkout -b <name> <sha>` |
| `reset --hard` lost commits | `git reflog` shows every HEAD move; `git reset --hard <sha>` to return |
| Pushed secrets | Immediately revoke the secret, then rewrite history with `git filter-repo` (preferred) or BFG; force-push; notify the team |

`git reflog` is the safety net — it logs every HEAD change for ~90 days. If the working tree is gone but you committed, it's recoverable.
