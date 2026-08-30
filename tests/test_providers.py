from colouring_factory.providers import (
    DEFAULT_PROVIDER,
    PROVIDERS,
    get_provider,
    provider_id_from_label,
)


def test_every_provider_is_completely_described() -> None:
    for provider_id, spec in PROVIDERS.items():
        assert spec.id == provider_id
        assert spec.label.strip()
        assert spec.env_var.strip()
        assert spec.key_url.startswith("https://")
        assert spec.billing_url.startswith("https://")
        assert spec.models, f"{provider_id} lists no models"
        assert spec.default_model in spec.models
        assert spec.portrait_size.strip()
        assert spec.square_size.strip()


def test_provider_labels_are_unique() -> None:
    labels = [spec.label.lower() for spec in PROVIDERS.values()]
    assert len(labels) == len(set(labels))


def test_default_provider_exists() -> None:
    assert DEFAULT_PROVIDER in PROVIDERS


def test_unknown_provider_falls_back_to_the_default() -> None:
    assert get_provider("nonsense").id == DEFAULT_PROVIDER
    assert get_provider(None).id == DEFAULT_PROVIDER
    assert provider_id_from_label("Nonsense") == DEFAULT_PROVIDER


def test_label_round_trips_to_its_own_id() -> None:
    for provider_id, spec in PROVIDERS.items():
        assert provider_id_from_label(spec.label) == provider_id


def test_every_provider_declares_a_text_model_and_seed_support() -> None:
    for spec in PROVIDERS.values():
        assert isinstance(spec.text_model, str)
        assert isinstance(spec.supports_seed, bool)


def test_google_is_available_with_a_text_model() -> None:
    assert "google" in PROVIDERS
    google = PROVIDERS["google"]
    assert google.text_model == "gemini-3.5-flash-lite"
    assert google.default_model == "gemini-3.1-flash-image"
    assert google.portrait_size == "3:4"
    assert google.square_size == "1:1"


def test_recraft_has_no_text_model_but_supports_seeds() -> None:
    assert PROVIDERS["recraft"].text_model == ""
    assert PROVIDERS["recraft"].supports_seed is True


def test_openai_has_a_text_model_and_no_seed() -> None:
    assert PROVIDERS["openai"].text_model == "gpt-5-mini"
    assert PROVIDERS["openai"].supports_seed is False


def test_every_provider_has_its_own_setup_instructions() -> None:
    # A two-way if/else in the interface silently gave Gemini users Recraft's
    # instructions, so the copy now lives with the provider it describes.
    hints = {}
    for provider_id, spec in PROVIDERS.items():
        assert spec.setup_hint.strip(), f"{provider_id} has no setup hint"
        assert spec.billing_button_label.strip()
        hints[provider_id] = spec.setup_hint

    assert len(set(hints.values())) == len(hints), "two providers share a setup hint"


def test_no_setup_hint_names_a_different_provider() -> None:
    for provider_id, spec in PROVIDERS.items():
        for other_id, other in PROVIDERS.items():
            if other_id == provider_id:
                continue
            assert other.label.lower() not in spec.setup_hint.lower(), (
                f"{provider_id}'s instructions mention {other.label}"
            )
