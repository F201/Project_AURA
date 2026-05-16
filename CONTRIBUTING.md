# 🤝 Contributing to AURA

Thank you for your interest in contributing to **Project AURA (Advanced Universal Responsive Avatar)**! We are building the future of local-first AI companions.

We use a **GitHub-based workflow** with feature branches, pull requests (PRs), and core reviewer approvals.

---

## 📌 Branch Naming Convention

Branches must be named clearly and consistently corresponding to their component:

- **feature/** → for new features  
  - `feature/dashboard-ui-upgrade`
  - `feature/voice-japanese-support`
- **fix/** → for bug fixes  
  - `fix/livekit-rtc-disconnect`
  - `fix/pgvector-indexing`
- **chore/** → for non-functional/documentation changes
  - `chore/update-readme`
  - `chore/mkdocs-theme`

---

## 💻 Local Development
For detailed local setup instructions, component architecture, and API documentation, please visit our documentation website or view the markdown files located in `docs/developer/`.

---

## 🔀 Pull Request (PR) Format

When opening a PR, follow this format:

### Title
`[type]: Short description`

Examples:

- `feature: add system prompt memory chunking`
- `fix: resolve livekit token expiration issue`

### Description
Your PR description should include:
1. **Summary** — What does this PR do?
2. **Testing** — Detail exactly what scripts or Pytests you ran to ensure this didn't break latency or functionality.
3. **Screenshots** (if applicable) — If modifying the Dashboard or the Live2D Avatar parameters, attach a screenshot/video.

---

## ⚖️ License
By contributing to AURA, you agree that your contributions will be licensed under its MIT License.