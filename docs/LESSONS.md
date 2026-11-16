# Lessons

Mistakes, surprises and how they were handled. Newest at the bottom.

## 2026-11-16 Remote was empty

The brief said the GitHub repo already had a README commit on `main`. `git clone`
reported an empty repository and the API showed size 0 with no branches. The first
commit (repo hygiene, hooks, docs and README) was therefore made locally and pushed
as the root of `main`. Lesson: check `gh api repos/<owner>/<repo>/branches` before
assuming history exists.

## 2026-11-16 Local default branch is master

The global `init.defaultBranch` on this machine is `master`. The local branch was
created as `main` explicitly. Lesson: never rely on defaults for branch names here.

## 2026-11-16 A broken editor plugin hook blocked every tool call

A telemetry hook from an editor plugin pointed at a missing file, and every command
and file read failed before running. Nothing in the repo was wrong. The owner fixed
the plugin; work resumed. Lesson: if every call fails with the same hook error, stop
and report it rather than working around it.

## 2026-11-16 Pin exact release tag when an action lacks a floating major tag

`astral-sh/setup-uv` published `v10.3.3` without a floating `v10` tag, causing the CI
runner to fail action resolution. Fixed by pinning `@v10.3.3`. Lesson: use the exact
tag returned by `gh api repos/<owner>/<repo>/releases/latest --jq .tag_name` unless the
floating major tag is verified to exist.

## 2026-11-17 No background installs; foreground with timeout

Starlette's synchronous `TestClient` (which spawns an `anyio` BlockingPortal thread/pipe
under the hood) hung inside the Windows sandbox when `pytest` was backgrounded. Fixed by
making the FastAPI route handlers synchronous and invoking them directly in unit tests,
keeping heavy training dependencies in an optional `train` group (`uv sync --extra train`,
pinned to the PyTorch CPU index locally), and never running installs or tests in the
background: no background installs; foreground with timeout.


