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
    # Kept per provider rather than branched on in the interface, where a
    # two-way if/else silently gave Gemini users Recraft's instructions.
    setup_hint: str = ""
    billing_button_label: str = "Open API pricing"
    supports_edit: bool = False
    # One scale, 1.0 meaning "stay as close to the original as possible".
    # Recraft's strength runs backwards and OpenAI's input_fidelity is two
    # words, so each adapter translates rather than storing raw values.
    # gpt-image-2 ignores this because it always works at high fidelity, which
    # is the end of the scale Doodle asks for anyway.
    edit_closeness: float = 0.85


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
        setup_hint=(
            "On the OpenAI page, create a new secret key, name it Doodle, and copy it "
            "while it is visible, then return here. ChatGPT and API billing are separate, "
            "so a ChatGPT subscription does not pay for this."
        ),
        billing_button_label="Open API billing",
        supports_edit=True,
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
        setup_hint=(
            "On the Google AI Studio page, select Create API key, choose or create a "
            "project, then copy the key and return here. The free allowance needs no "
            "card."
        ),
        billing_button_label="Open usage and billing",
        supports_edit=True,
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
        setup_hint=(
            "Add API units in Recraft first, then open Profile → API, generate a token, "
            "copy it and return here. Recraft will not issue a token on a zero balance."
        ),
        billing_button_label="Open API pricing",
        supports_edit=True,
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
