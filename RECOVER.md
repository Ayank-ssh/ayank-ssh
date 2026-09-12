# Git recovery

Your local branch is currently inside an interrupted rebase.

1. Abort it:
   `git rebase --abort`

2. Refresh the remote:
   `git fetch origin`

3. Reset the local branch to the remote:
   `git reset --hard origin/main`

4. Copy this package's files over the repo again.

5. Commit and push:
   `git add .`
   `git commit -m "Polish profile README and graph"
   git push`

This discards only local commits that are already superseded by origin/main.
