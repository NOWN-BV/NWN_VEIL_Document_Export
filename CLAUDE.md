# NWN_VEIL_Document_Export

## Merging PRs (Claude sessions)

`.claude/settings.json` allows `gh pr merge`, so local and cloud sessions can merge without the auto-mode
"Merge Without Review" block. The rule only matches the merge run as one command on its own: no `cd ... &&`,
no pipes, no `gh api .../merge`. Use `--repo` instead of `cd`, e.g. `gh pr merge 123 --merge --repo NOWN-BV/<repo>`.
The branch rules in this file still decide which merges are allowed.
