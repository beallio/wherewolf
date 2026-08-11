import re
from pathlib import Path

WORKFLOW = Path(".github/workflows/release.yml")
CHANGELOG = Path("CHANGELOG.md")


def _job_block(workflow: str, job_name: str) -> str:
    pattern = rf"^  {re.escape(job_name)}:\n(?P<body>.*?)(?=^  [\w-]+:\n|\Z)"
    match = re.search(pattern, workflow, flags=re.MULTILINE | re.DOTALL)
    assert match, f"release job {job_name!r} is missing"
    return match.group("body")


def test_github_release_is_titled_and_bodied_from_the_changelog() -> None:
    """A published release must carry the human-readable notes, not just a compare link.

    `generate_release_notes: true` alone yields a bare tag title and an auto-generated
    body, which is what shipped for v0.8.0 and had to be corrected by hand.
    """
    job = _job_block(WORKFLOW.read_text(encoding="utf-8"), "github-release")

    assert "body_path:" in job, "the release body must come from a file, not be auto-generated"
    assert "name:" in job, (
        "the release must set an explicit title rather than defaulting to the tag"
    )
    assert "CHANGELOG.md" in job, "the release notes must be extracted from CHANGELOG.md"


def test_changelog_documents_the_packaged_version() -> None:
    """The extraction step has nothing to find if the version was never written up."""
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    version_match = re.search(r'^version = "(?P<version>[^"]+)"', pyproject, flags=re.MULTILINE)
    assert version_match, "pyproject.toml must declare a static version"
    version = version_match.group("version")

    changelog = CHANGELOG.read_text(encoding="utf-8")
    assert f"## [{version}]" in changelog, (
        f"CHANGELOG.md has no section for the packaged version {version}; "
        "the release workflow would publish an empty body"
    )


def test_changelog_section_extraction_yields_only_that_release() -> None:
    """Pin the awk contract the workflow relies on: one section, not the whole file."""
    changelog = CHANGELOG.read_text(encoding="utf-8")
    sections = re.findall(
        r"^## \[(?P<version>[^\]]+)\][^\n]*\n(?P<body>.*?)(?=^## \[|\Z)",
        changelog,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert len(sections) >= 2, "expected several released versions to be documented"

    versions = [version for version, _ in sections]
    assert versions == sorted(
        versions, key=lambda v: [int(p) for p in v.split(".")], reverse=True
    ), "CHANGELOG sections must stay newest-first so the extractor takes the right one"

    newest_version, newest_body = sections[0]
    assert f"## [{newest_version}]" not in newest_body
    for older_version, _ in sections[1:]:
        assert f"## [{older_version}]" not in newest_body, (
            "extracting the newest section must not bleed into older releases"
        )
