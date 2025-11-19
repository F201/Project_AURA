# 🤝 Contributing Guidelines

Thank you for considering contributing to **AI Helpdesk Backend**!  
We use a **GitHub-based workflow** with feature branches, pull requests (PRs), and code reviews.  
This document explains the conventions for contributing.

---

## 📌 Branch Naming Convention

Branches must be named clearly and consistently:

- **feature/** → for new features  
  - `feature/auth-otp`
  - `feature/kb-indexing`
- **fix/** → for bug fixes  
  - `fix/login-timeout`
  - `fix/docker-compose-path`
- **chore/** → for non-functional changes (docs, configs, CI/CD)  
  - `chore/update-readme`
  - `chore/linting`

---

## 🔀 Pull Request (PR) Format

When opening a PR, follow this format:

### Title
[type]: Short description

Examples:
- `feature: add system prompt for the LLM`
- `fix: resolve docker build issue for front-end`
- `chore: update contributing guidelines`

### Description
Your PR description should include:
1. **Summary** — What does this PR do?
2. **Changes** — Key changes made (list of files/features).
3. **Testing** — How to test it locally.
4. **Related Issues** — Link any GitHub issues (if applicable).

Example:
```markdown
## Summary
Implemented a system prompt for the LLM

## Changes
- Added a persona prompt pattern for Aura

## Testing
- Run `docker compose up`
- Test with `GET /api/aura`

## Related Issues
Closes #12