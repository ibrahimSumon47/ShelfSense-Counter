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
