# GitHub Remote & Automated Release Plan

## Objective
Establish a robust GitHub remote repository with automated CI/CD pipelines for testing, linting, and multi-platform releases (GitHub & PyPI).

## Architecture Overview
- **Source Control:** GitHub (Git).
- **CI/CD Platform:** GitHub Actions.
- **Dependency Management:** `uv`.
- **Build System:** `hatchling`.
- **Release Targets:** GitHub Releases (with auto-changelog) and PyPI.
- **Security:** OIDC (OpenID Connect) for PyPI (Trusted Publishers).

## Implementation Steps

### 1. Repository Setup
1. **Create GitHub Repository:**
   ```bash
   gh repo create wherewolf --public --source=. --remote=origin --push
   ```
2. **Configure Branch Protection:**
   Set `main` as a protected branch requiring status checks (CI) to pass.

### 2. Versioning Strategy
We will use `hatch` to manage versioning within `pyproject.toml`.
- Current version: `0.1.0`.
- To increment: `uv run hatch version minor` (or patch/major).

### 3. GitHub Actions Workflows

#### A. Continuous Integration (`.github/workflows/ci.yml`)
- Trigger: Push to `main`, Pull Requests to `main`.
- Jobs:
  - **Linting:** `ruff check` and `ruff format --check`.
  - **Testing:** `pytest` across supported Python versions (3.11+).

#### B. Automated Release (`.github/workflows/release.yml`)
- Trigger: Push of tags matching `v*.*.*`.
- Jobs:
  - **Build:** Create source distribution and wheel using `uv build`.
  - **Release:** 
    - Create a GitHub Release using `softprops/action-gh-release`.
    - Auto-generate the changelog from commit messages/PRs.
  - **Publish:**
    - Upload artifacts to PyPI.
    - Uses OIDC for authentication (no `PYPI_API_TOKEN` secret required).

### 4. PyPI Trusted Publisher Setup
1. Log into PyPI.
2. Navigate to **Publishing** -> **Add a new GitHub publisher**.
3. Configure for `wherewolf` repository and the `release.yml` workflow.

### 5. Automation Tools
- **Changelog Generation:** Use GitHub's built-in `generate_release_notes: true` feature.

## Verification & Testing
1. **CI Check:** Push a commit and verify the `ci.yml` workflow passes.
2. **Production Release:** Push a production tag (e.g., `v0.1.1`) and verify:
   - GitHub Release created with changelog.
   - Package available on PyPI.

## Documentation
- Create `docs/RELEASING.md` for manual release steps (version bumping).
- Update `README.md` with CI/Release status badges.
