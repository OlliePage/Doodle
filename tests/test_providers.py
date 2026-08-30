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
