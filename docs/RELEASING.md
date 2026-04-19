# Releasing Wherewolf

This project uses GitHub Actions to automate releases to GitHub and PyPI whenever a new version tag is pushed.

## Release Process

### 1. Prepare the Release
Ensure all changes are committed and tests pass locally.

```bash
uv run pytest
ruff check .
```

### 2. Bump the Version
Use `hatch` (via `uv`) to increment the version in `pyproject.toml`.

```bash
# Options: patch, minor, major
uv run hatch version patch
```

### 3. Commit and Tag
Commit the version bump and create a git tag.

```bash
# Get the new version string
VERSION=$(uv run hatch version)

# Commit the version bump
git add pyproject.toml
git commit -m "chore: bump version to $VERSION"

# Create a tag
git tag -a "v$VERSION" -m "Release v$VERSION"
```

### 4. Push to GitHub
Push both the commit and the tag to GitHub.

```bash
git push origin main --follow-tags
```

## What Happens Next?
- **CI Workflow:** Runs tests and linting.
- **Release Workflow:** 
  1. Builds the wheel and source distribution.
  2. Creates a GitHub Release with an auto-generated changelog.
  3. Publishes the package to PyPI using Trusted Publishers (OIDC).

## Troubleshooting

### PyPI Publishing Fails
- Ensure the project is configured as a **Trusted Publisher** on PyPI.
- Go to PyPI -> Settings -> Publishing -> Add GitHub Publisher.
- Organization: `beallio` (or your username/org)
- Repository: `wherewolf`
- Workflow name: `release.yml`
- Environment name: `pypi`
