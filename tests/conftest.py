import pytest


@pytest.fixture(autouse=True)
def crate_home(tmp_path, monkeypatch):
    """Every test gets an isolated ~/.crate."""
    home = tmp_path / "crate-home"
    monkeypatch.setenv("CRATE_HOME", str(home))
    from crate import config

    config.ensure_dirs()
    return home
