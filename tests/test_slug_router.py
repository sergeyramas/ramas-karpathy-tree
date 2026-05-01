from pathlib import Path

from scripts.slug_router import resolve_slug

FIXTURE = Path(__file__).parent / "fixtures" / "projects.json"


def test_exact_match():
    assert resolve_slug("/tmp/alpha", FIXTURE) == "alpha"


def test_subdir_match():
    assert resolve_slug("/tmp/alpha/some/file.py", FIXTURE) == "alpha"


def test_longest_prefix_wins():
    # /tmp/alpha/sub/deep should match "deep" not "alpha"
    assert resolve_slug("/tmp/alpha/sub/deep/x.py", FIXTURE) == "deep"


def test_alternate_prefix():
    assert resolve_slug("/tmp/beta-worktree/x.py", FIXTURE) == "beta"


def test_fallback():
    assert resolve_slug("/var/log/system.log", FIXTURE) == "_global"


def test_empty_cwd():
    assert resolve_slug("", FIXTURE) == "_global"


def test_missing_config_falls_back():
    assert resolve_slug("/tmp/alpha", Path("/nonexistent/projects.json")) == "_global"
