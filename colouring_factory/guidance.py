from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Guidance:
    title: str
    cause: str
    fix: str
    control: str
    action_label: str = ""


_SETTINGS = "the Settings sidebar"
_CONNECT = "the Connect an image generator screen"

_ENTRIES: dict[str, Guidance] = {
    "missing_key": Guidance(
        title="No image generator is connected",
        cause="Doodle needs a key from an image provider before it can draw anything.",
        fix=(
            "Connect a provider. Google Gemini has a free allowance if you would rather "
            "not add a card."
        ),
        control=_CONNECT,
        action_label="Connect a provider",
    ),
    "authentication": Guidance(
        title="That key was not accepted",
        cause=(
            "The provider rejected the key, usually because it was revoked, mistyped or "
            "truncated when copied."
        ),
        fix="Create a fresh key on the provider's site and paste it again.",
        control=_CONNECT,
        action_label="Replace the key",
    ),
    "billing": Guidance(
        title="The provider has no credit",
        cause="The key works, but the account has no billing method or no remaining balance.",
        fix="Add billing or top up the account, then try the same key again.",
        control=_CONNECT,
        action_label="Open billing",
    ),
    "verification": Guidance(
        title="The account is not yet verified",
        cause=(
            "The provider withholds image generation until the account or organisation "
            "is verified."
        ),
        fix="Finish verification on the provider's site, then use the same key again.",
        control=_CONNECT,
        action_label="Open the provider",
    ),
    "permission": Guidance(
        title="That key cannot generate images",
        cause="The key is recognised, but its permissions exclude image generation.",
        fix="Create a key with image permissions, or use an unrestricted one.",
        control=_CONNECT,
        action_label="Replace the key",
    ),
    "rate_limit": Guidance(
        title="The provider is asking you to slow down",
        cause="Too many requests arrived in a short time.",
        fix="Wait a minute and draw again. Asking for fewer alternatives at once also helps.",
        control="Alternatives, on the generation form",
    ),
    "content": Guidance(
        title="The provider declined that description",
        cause=(
            "A safety filter matched something in the wording, often a real character or "
            "brand name."
        ),
        fix=(
            "Describe the picture in your own words instead of naming a character from "
            "television or film."
        ),
        control="Picture idea, on the generation form",
    ),
    "network": Guidance(
        title="Doodle could not reach the provider",
        cause="The request did not complete, usually a dropped connection or a provider outage.",
        fix="Check the internet connection and draw again.",
        control="the generation form",
    ),
    "unsupported_provider": Guidance(
        title="That provider is not available",
        cause="The saved provider is not one Doodle knows about, probably from an older version.",
        fix="Choose a provider again.",
        control=_SETTINGS,
        action_label="Choose a provider",
    ),
    "missing_prompt": Guidance(
        title="No picture idea yet",
        cause="Doodle has nothing to draw until you describe something.",
        fix=(
            "Type what you would like drawn, such as a smiling baby dinosaur washing a "
            "toy fire engine."
        ),
        control="Picture idea, on the generation form",
    ),
    "brief_format": Guidance(
        title="The alternatives could not be planned",
        cause=(
            "The text model returned scenes Doodle could not read, so the built-in "
            "variations were used instead."
        ),
        fix="Nothing to do. The pictures will still differ, using Doodle's own variation rules.",
        control="Alternatives, on the generation form",
    ),
    "brief_failed": Guidance(
        title="The alternatives could not be planned",
        cause=(
            "The text model could not be reached, so the built-in variations were used "
            "instead."
        ),
        fix="Nothing to do. The pictures will still differ, using Doodle's own variation rules.",
        control="Alternatives, on the generation form",
    ),
    "no_text_model": Guidance(
        title="This provider cannot plan the alternatives",
        cause="The chosen provider only draws pictures, so Doodle used its own variation rules.",
        fix="Switch to OpenAI or Google Gemini for more varied alternatives.",
        control=_SETTINGS,
    ),
    "no_circles_fit": Guidance(
        title="No badges fit on the sheet",
        cause="The cut diameter plus the outer margin is wider than the page.",
        fix="Reduce the outer margin or the cut diameter.",
        control="Outer margin, on the circle sheet form",
    ),
    "badge_too_large": Guidance(
        title="The badge is wider than the page",
        cause=(
            "No margin can help, because the cut diameter alone is as wide as the shorter "
            "side of the page."
        ),
        fix="Reduce the paper cut diameter to less than 210 mm.",
        control="Paper cut diameter, on the circle sheet form",
    ),
    "invalid_circle_geometry": Guidance(
        title="Those three diameters cannot all be true",
        cause=(
            "The safe area must fit inside the finished face, and the finished face inside "
            "the paper cut."
        ),
        fix="Set safe smaller than finished, and finished no larger than the paper cut.",
        control="the three diameter boxes on the circle sheet form",
    ),
    "too_much_ink": Guidance(
        title="This picture is very heavy on black",
        cause=(
            "Over a third of the page is solid black, which drinks ink and leaves little "
            "to colour in."
        ),
        fix="Lower the black and white threshold, or choose a simpler picture.",
        control="Black/white threshold, in Step 2",
        action_label="Lower the threshold",
    ),
    "too_little_ink": Guidance(
        title="Almost no line work survived",
        cause="The threshold is discarding lines that are too faint to register as black.",
        fix="Raise the black and white threshold until the outlines return.",
        control="Black/white threshold, in Step 2",
        action_label="Raise the threshold",
    ),
    "pdf_failed": Guidance(
        title="The PDF could not be built",
        cause="The page dimensions and margins leave no room for the artwork.",
        fix="Reduce the inner margin, or increase the page size.",
        control="the layout form in Step 3",
    ),
    "edit_unsupported": Guidance(
        title="This provider cannot change a picture",
        cause="The chosen provider can draw a new picture but not modify an existing one.",
        fix="Switch provider, or draw a new picture with the change described in the idea.",
        control=_SETTINGS,
        action_label="Choose a provider",
    ),
    "edit_failed": Guidance(
        title="The change could not be made",
        cause="The provider accepted the request but returned no changed picture.",
        fix=(
            "Try describing the change in fewer, plainer words. The picture you had "
            "is unchanged."
        ),
        control="Make a change, beneath the picture",
    ),
    "photo_declined": Guidance(
        title="The provider would not draw from that picture",
        cause=(
            "The drawing service ran its own check on the picture and declined "
            "it. Doodle does not know which part it objected to."
        ),
        fix=(
            "Try a different picture of the same character, or untick them and "
            "let the written description do the work."
        ),
        control="Your characters, on the homepage",
    ),
    "no_reference_support": Guidance(
        title="This drawing service cannot draw from a picture",
        cause="Recraft accepts one picture per request, so it cannot carry a cast.",
        fix="Connect OpenAI or Google Gemini to draw your characters.",
        control="Change image provider, on the result screen",
    ),
    "too_many_references": Guidance(
        title="That is more characters than this service will look at",
        cause="Each drawing service has its own limit on reference pictures.",
        fix="Untick some characters and draw again.",
        control="Your characters, on the homepage",
    ),
    "unknown": Guidance(
        title="Something went wrong",
        cause="Doodle did not recognise this failure.",
        fix="Try again. If it keeps happening, check the provider connection.",
        control=_SETTINGS,
    ),
}

GUIDANCE_CODES = frozenset(_ENTRIES)


def guidance_for(code: str, **context: Any) -> Guidance:
    """Explain a failure and, where possible, name the correction.

    An unrecognised code returns the generic entry rather than None, so no
    failure can reach the user without an explanation.
    """

    entry = _ENTRIES.get(code, _ENTRIES["unknown"])

    margin = context.get("suggested_margin_mm")
    if code == "no_circles_fit" and margin is not None:
        return Guidance(
            title=entry.title,
            cause=entry.cause,
            fix=f"An outer margin of {margin:g} mm would leave room for at least one badge.",
            control=entry.control,
            action_label=f"Set the margin to {margin:g} mm",
        )

    return entry
