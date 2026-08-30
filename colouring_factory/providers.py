from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    label: str
    env_var: str
    key_url: str
    billing_url: str
    docs_url: str
    default_model: str
    models: tuple[str, ...]
    portrait_size: str
    square_size: str
    key_placeholder: str
    description: str
    billing_note: str


PROVIDERS: dict[str, ProviderSpec] = {
    "openai": ProviderSpec(
        id="openai",
        label="OpenAI",
        env_var="OPENAI_API_KEY",
        key_url="https://platform.openai.com/settings/organization/api-keys",
        billing_url="https://platform.openai.com/settings/organization/billing/overview",
        docs_url="https://developers.openai.com/api/docs/guides/image-generation",
        default_model="gpt-image-2",
        models=("gpt-image-2", "gpt-image-1.5", "gpt-image-1-mini"),
        portrait_size="1024x1536",
        square_size="1024x1024",
        key_placeholder="sk-proj-…",
        description="Best prompt-following and the simplest starting point.",
        billing_note="ChatGPT and the API are billed separately. API billing must be enabled.",
    ),
    "recraft": ProviderSpec(
        id="recraft",
        label="Recraft",
        env_var="RECRAFT_API_TOKEN",
        key_url="https://app.recraft.ai/profile/api",
        billing_url="https://www.recraft.ai/pricing?tab=api",
        docs_url="https://www.recraft.ai/docs/api-reference/getting-started",
        default_model="recraftv4_1",
        models=("recraftv4_1", "recraftv4_1_utility", "recraftv4"),
        portrait_size="3:4",
        square_size="1:1",
        key_placeholder="Paste your Recraft API token",
        description="Strong illustration control and useful deterministic seed support.",
        billing_note="Recraft requires a positive API-unit balance before it will issue a token.",
    ),
}

DEFAULT_PROVIDER = "openai"


def get_provider(provider_id: str | None) -> ProviderSpec:
    return PROVIDERS.get(str(provider_id or "").lower(), PROVIDERS[DEFAULT_PROVIDER])


def provider_labels() -> list[str]:
    return [spec.label for spec in PROVIDERS.values()]


def provider_id_from_label(label: str) -> str:
    wanted = label.strip().lower()
    for provider_id, spec in PROVIDERS.items():
        if spec.label.lower() == wanted:
            return provider_id
    return DEFAULT_PROVIDER
