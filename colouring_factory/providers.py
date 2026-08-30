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
    text_model: str = ""
    supports_seed: bool = False


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
        text_model="gpt-5-mini",
        supports_seed=False,
    ),
    "google": ProviderSpec(
        id="google",
        label="Google Gemini",
        env_var="GEMINI_API_KEY",
        key_url="https://aistudio.google.com/apikey",
        billing_url="https://aistudio.google.com/usage",
        docs_url="https://ai.google.dev/gemini-api/docs/image-generation",
        default_model="gemini-3.1-flash-image",
        models=(
            "gemini-3.1-flash-image",
            "gemini-3.1-flash-lite-image",
            "gemini-3-pro-image",
        ),
        portrait_size="3:4",
        square_size="1:1",
        key_placeholder="AIza…",
        description="Has a free tier, so it is the cheapest way to start.",
        billing_note="A free allowance covers occasional use; heavier use needs billing enabled.",
        text_model="gemini-3.5-flash-lite",
        supports_seed=False,
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
        text_model="",
        supports_seed=True,
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
