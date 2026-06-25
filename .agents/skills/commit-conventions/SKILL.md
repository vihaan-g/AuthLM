---
name: commit-conventions
description: Use when creating, reviewing, rewriting, squashing, fixing, amending, signing, or pushing Git commits, commit messages, conventional commits, DCO sign-off, or release/version history.
---

# Commit Conventions

Use these rules for commits in this project. Source reference: https://github.com/netresearch/git-workflow-skill/blob/main/skills/git-workflow/references/commit-conventions.md

## Format

Use Conventional Commits:

```text
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.

Use `feat` for minor releases, `fix` and `perf` for patch releases, and `!` plus `BREAKING CHANGE:` for major releases.

## Subject

Write the subject in imperative, present tense: `add`, `fix`, `remove`, not `added`, `fixed`, or `removes`.

Keep the subject specific, concise, under 72 characters, and without a trailing period.

Use a lowercase kebab-case scope when it adds useful context, such as `fix(api): handle empty response`.

Never use vague messages like `wip`, `fix stuff`, `updates`, or `improve API`.

Do not use emojis in commit messages.

## Body And Footers

Add a body when the change needs context, motivation, tradeoffs, or future-reader explanation.

Wrap body lines at about 72 characters where practical.

Put issue references and metadata in footers, such as `Fixes #123`, `Refs: #456`, `Reviewed-by: Name`, and `Co-authored-by: Name <email>`.

For breaking changes, include a footer beginning exactly with `BREAKING CHANGE:`.

For multiline or special-character commit bodies, write the message from a file or single-quoted heredoc instead of double-quoted `-m` strings.

```bash
git commit -S --signoff -F - <<'EOF'
fix: prevent race condition in order processing

Body may contain "quotes", & ampersands, `backticks`, and $vars literally.
EOF
```

## Atomic Commits

Make each commit one self-contained logical change that builds and passes relevant tests independently.

Do not mix unrelated concerns, such as feature work, typos, and dependency updates in one commit.

Stage only intended files or hunks. Do not use `git add .` unless every changed file belongs to the same logical commit.

Rewrite messy local history before opening a PR when explicitly requested or appropriate for the workflow.

## Signing And Sign-Off

Use signed commits with DCO sign-off:

```bash
git commit -S --signoff -m "fix: prevent duplicate submissions"
```

Use explicit `-S` so Git fails loudly if signing is unavailable.

Use `--signoff` so Git adds the `Signed-off-by:` trailer required by DCO checks.

Before committing in a new worktree, verify identity is sane:

```bash
git config user.name
git config user.email
```

`user.name` must be a human name, not an email address. `user.email` must be an email address.

Never bypass signing with `--no-gpg-sign` or disabled signing config unless explicitly requested.

Never skip hooks with `--no-verify` unless explicitly requested.

If a pre-commit hook fails, the commit did not happen. Fix the hook issue, re-stage, and create a new commit. Do not run `git commit --amend` after a failed commit attempt.

## Pushes

On the first push of a new branch, set upstream tracking:

```bash
git push -u origin feature-branch
```

After upstream tracking exists, use normal `git push` and `git pull`.

## Common Mistakes

Do not leave `fixup!`, `squash!`, or scratch commits in PR history.

Do not include generated files unless the project expects them.

Do not create probe commits on the default branch to test signing. Inspect config instead, or use a throwaway branch if an actual signing test is required.
