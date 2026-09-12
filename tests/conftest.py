from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolated_doodle_data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    # A default so a test that forgets to point storage elsewhere still can't
    # write into the real ~/.doodle; tests that set DOODLE_DATA_DIR themselves
    # simply overwrite this before storage.data_root() is ever called.
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "doodle-data"))
