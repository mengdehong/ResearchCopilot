---
trigger: always_on
glob:
description:
---
- Perform only if explicitly requested by the user
- Commit messages: `type(scope): short description` (e.g., `feat(ui): add tier drag-drop`,
  `fix(rag): rank compression edge case`, `refactor(core): extract shelf repository`).
- Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `style`, `ci`.
- Keep commits atomic — one logical change per commit.  

