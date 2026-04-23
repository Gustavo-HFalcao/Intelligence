---
name: clean-git-commits
description: "Enforces Conventional Commits to keep the automated AI agent git history clean and traceable."
---

# Clean Git Commits

Automated agents often ruin a repository's git history by pushing non-descriptive messages like "Fix bug" or "Update code". 

## 1. Use Conventional Commits
All commits MUST follow the conventional commit structure:
`type(scope): description`

### Valid Types:
- `feat:` (New feature)
- `fix:` (Bug fix)
- `refactor:` (Code rewrite without behavior change)
- `chore:` (Dependencies, skills configuration, etc)
- `docs:` (Documentation updates)

## 2. Examples
- **BAD**: `git commit -m "added the voice chart"`
- **GOOD**: `git commit -m "feat(audio): implement hands-free voice-to-chart processing"`

- **BAD**: `git commit -m "fixed stuff"`
- **GOOD**: `git commit -m "fix(auth): correct the supabase environment variables to production"`
