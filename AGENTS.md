# Repository Guidelines

- **Testing:** After making any changes, install dependencies and run the unit tests:
  ```bash
  pip install -r requirements.txt
  pytest -q
  ```
  All tests should pass before committing.
- **Reference:** Consult `README.md` for project overview, usage instructions, and directory layout.
- **Code Style:** Follow standard PEP 8 conventions and keep new modules under `src/`. Update documentation when behavior changes.
