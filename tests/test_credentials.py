import stat

import pytest

from colouring_factory.credentials import (
    credentials_path,
    delete_provider_key,
    load_credentials,
    mask_key,
    resolve_provider_key,
    save_provider_key,
)


@pytest.fixture(autouse=True)
def isolated_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("RECRAFT_API_TOKEN", raising=False)


def test_a_saved_key_is_read_back() -> None:
    save_provider_key("openai", "sk-test-12345678")
    assert load_credentials()["openai"] == "sk-test-12345678"


def test_the_credentials_file_is_readable_only_by_its_owner() -> None:
    save_provider_key("openai", "sk-test-12345678")
    mode = credentials_path().stat().st_mode
    assert not mode & stat.S_IRGRP
    assert not mode & stat.S_IROTH


def test_an_empty_key_is_refused() -> None:
    with pytest.raises(ValueError):
        save_provider_key("openai", "   ")


def test_deleting_the_last_key_removes_the_file() -> None:
    save_provider_key("openai", "sk-test-12345678")
    delete_provider_key("openai")
    assert not credentials_path().exists()


def test_deleting_one_of_two_keys_keeps_the_other() -> None:
    save_provider_key("openai", "sk-test-12345678")
    save_provider_key("recraft", "recraft-token-abcdefgh")
    delete_provider_key("openai")
    assert load_credentials() == {"recraft": "recraft-token-abcdefgh"}


def test_session_beats_environment_which_beats_disk(monkeypatch) -> None:
    save_provider_key("openai", "sk-from-disk-000000")
    key, source = resolve_provider_key("openai")
    assert key == "sk-from-disk-000000"
    assert source == "this Mac"

    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env-000000")
    key, source = resolve_provider_key("openai")
    assert key == "sk-from-env-000000"
    assert source == "OPENAI_API_KEY"

    key, source = resolve_provider_key("openai", {"openai": "sk-from-session-0000"})
    assert key == "sk-from-session-0000"
    assert source == "this session"


def test_no_key_anywhere_returns_empty() -> None:
    assert resolve_provider_key("openai") == ("", "")


def test_a_corrupt_credentials_file_is_treated_as_empty() -> None:
    save_provider_key("openai", "sk-test-12345678")
    credentials_path().write_text("{ not json", encoding="utf-8")
    assert load_credentials() == {}


def test_masking_never_reveals_the_middle_of_a_key() -> None:
    assert mask_key("sk-proj-abcdefghijklmnop") == "sk-p••••mnop"
    assert mask_key("short") == "••••••••"
    assert mask_key("") == ""
