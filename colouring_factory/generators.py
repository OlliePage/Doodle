from __future__ import annotations

import base64
import json
import uuid
from collections.abc import Sequence
from io import BytesIO
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .models import GeneratedArtwork

GOOGLE_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
RECRAFT_EDIT_ENDPOINT = "https://external.api.recraft.ai/v1/images/imageToImage"


def _multipart_body(
    fields: dict[str, str], files: dict[str, tuple[str, bytes, str]]
) -> tuple[bytes, str]:
    """Encode a multipart/form-data body without adding a dependency."""

    boundary = f"----doodle{uuid.uuid4().hex}"
    parts: list[bytes] = []

    for name, value in fields.items():
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        parts.append(f"{value}\r\n".encode())

    for name, (filename, payload, content_type) in files.items():
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode()
        )
        parts.append(f"Content-Type: {content_type}\r\n\r\n".encode())
        parts.append(payload)
        parts.append(b"\r\n")

    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _check_instruction(prompt: str) -> str:
    instruction = prompt.strip()
    if not instruction:
        raise ValueError("Describe the change you would like.")
    return instruction


class GeneratorError(RuntimeError):
    """A provider failure that can be explained directly in the interface."""

    def __init__(
        self,
        message: str,
        *,
        provider: str = "",
        code: str = "unknown",
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.code = code
        self.status_code = status_code


def _normalise_error(
    provider: str,
    exc: Exception,
    *,
    status_code: int | None = None,
    details: str = "",
) -> GeneratorError:
    status = (
        status_code if status_code is not None else getattr(exc, "status_code", None)
    )
    raw = " ".join(part for part in (details, str(exc)) if part).lower()

    # Google documents 401 for a rejected key but returns 400 with "API key not
    # valid" for a malformed one, so the wording is matched as well as the code.
    if status == 401 or any(
        marker in raw
        for marker in (
            "incorrect api key",
            "invalid api key",
            "api key not valid",
            "api_key_invalid",
            "invalid token",
            "authentication",
        )
    ):
        return GeneratorError(
            f"{provider} did not accept that API key. Create a fresh key and paste it again.",
            provider=provider,
            code="authentication",
            status_code=status,
        )
    if any(
        marker in raw
        for marker in (
            "billing",
            "insufficient_quota",
            "insufficient quota",
            "credit balance",
            "api units",
            "payment",
        )
    ):
        return GeneratorError(
            f"{provider} needs API billing or available credits before it can draw this Doodle.",
            provider=provider,
            code="billing",
            status_code=status,
        )
    if any(
        marker in raw
        for marker in (
            "verify",
            "verification",
            "organisation verification",
            "organization verification",
        )
    ):
        return GeneratorError(
            f"{provider} requires account or organisation verification before image generation can be used.",
            provider=provider,
            code="verification",
            status_code=status,
        )
    if status == 403 or "permission" in raw or "not allowed" in raw:
        return GeneratorError(
            f"That {provider} key is recognised, but it is not allowed to generate images.",
            provider=provider,
            code="permission",
            status_code=status,
        )
    if (
        status == 429
        or "rate limit" in raw
        or "too many requests" in raw
        or "quota_exceeded" in raw
    ):
        return GeneratorError(
            f"{provider} is temporarily rate-limiting requests. Wait briefly, then try again.",
            provider=provider,
            code="rate_limit",
            status_code=status,
        )
    if any(
        marker in raw
        for marker in (
            "content policy",
            "safety system",
            "moderation",
            "safety violation",
        )
    ):
        return GeneratorError(
            "The image provider declined that description. Rephrase the idea and try again.",
            provider=provider,
            code="content",
            status_code=status,
        )
    if isinstance(exc, (URLError, TimeoutError, ConnectionError)) or any(
        marker in raw
        for marker in ("timed out", "connection", "network", "name resolution")
    ):
        return GeneratorError(
            f"Doodle could not reach {provider}. Check the internet connection and try again.",
            provider=provider,
            code="network",
            status_code=status,
        )

    return GeneratorError(
        f"{provider} image generation failed: {str(exc).strip() or 'unknown provider error'}",
        provider=provider,
        code="unknown",
        status_code=status,
    )


def _check_prompts(prompts: Sequence[str]) -> None:
    if not 1 <= len(prompts) <= 4:
        raise GeneratorError("Between one and four pictures can be drawn at once.")


def _read_image_payload(item: Any) -> bytes:
    if isinstance(item, dict):
        encoded = item.get("b64_json")
        url = item.get("url")
    else:
        encoded = getattr(item, "b64_json", None)
        url = getattr(item, "url", None)

    if encoded:
        try:
            return base64.b64decode(encoded)
        except (ValueError, TypeError) as exc:
            raise GeneratorError(
                "The image provider returned invalid base64 image data."
            ) from exc
    if url:
        try:
            with urlopen(str(url), timeout=120) as response:  # nosec B310 - provider-supplied URL.
                return response.read()
        except Exception as exc:
            raise _normalise_error("Image provider", exc) from exc
    raise GeneratorError("The image response contained neither base64 data nor a URL.")


def generate_with_openai(
    *,
    api_key: str,
    prompts: Sequence[str],
    model: str = "gpt-image-2",
    size: str = "1024x1536",
    quality: str = "low",
) -> list[GeneratedArtwork]:
    """Generate one or more images using the OpenAI Images API."""

    if not api_key.strip():
        raise GeneratorError(
            "Connect OpenAI with an API key before generating artwork.",
            provider="OpenAI",
            code="missing_key",
        )
    _check_prompts(prompts)

    try:
        from openai import OpenAI
    except (
        ImportError
    ) as exc:  # pragma: no cover - only possible in an incomplete installation.
        raise GeneratorError(
            "The OpenAI Python package is not installed. Run pip install -r requirements.txt."
        ) from exc

    try:
        client = OpenAI(api_key=api_key.strip(), timeout=240.0, max_retries=2)
    except Exception as exc:
        raise _normalise_error("OpenAI", exc) from exc

    images: list[GeneratedArtwork] = []
    for index, variant_prompt in enumerate(prompts):
        try:
            result = client.images.generate(
                model=model,
                prompt=variant_prompt,
                size=size,
                quality=quality,
                background="opaque",
            )
            if not result.data:
                raise GeneratorError(
                    "OpenAI returned no image data.", provider="OpenAI"
                )
            item = result.data[0]
            image_bytes = _read_image_payload(item)
        except GeneratorError:
            raise
        except Exception as exc:
            raise _normalise_error("OpenAI", exc) from exc

        metadata: dict[str, Any] = {
            "variant": index + 1,
            "size": size,
            "quality": quality,
        }
        revised_prompt = getattr(item, "revised_prompt", None)
        if revised_prompt:
            metadata["revised_prompt"] = revised_prompt

        images.append(
            GeneratedArtwork(
                image_bytes=image_bytes,
                prompt=variant_prompt,
                provider="OpenAI",
                model=model,
                metadata=metadata,
            )
        )

    return images


def generate_with_recraft(
    *,
    api_key: str,
    prompts: Sequence[str],
    model: str = "recraftv4_1",
    size: str = "3:4",
    random_seed: int | None = None,
) -> list[GeneratedArtwork]:
    """Generate raster artwork with the Recraft REST API."""

    if not api_key.strip():
        raise GeneratorError(
            "Connect Recraft with an API token before generating artwork.",
            provider="Recraft",
            code="missing_key",
        )
    _check_prompts(prompts)

    images: list[GeneratedArtwork] = []
    endpoint = "https://external.api.recraft.ai/v1/images/generations"

    for index, variant_prompt in enumerate(prompts):
        body: dict[str, Any] = {
            "prompt": variant_prompt,
            "model": model,
            "size": size,
            "n": 1,
            "response_format": "b64_json",
        }
        if random_seed is not None:
            body["random_seed"] = int(random_seed) + index

        request = Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key.strip()}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=240) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")
            except OSError:
                detail = ""
            raise _normalise_error(
                "Recraft", exc, status_code=exc.code, details=detail
            ) from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise _normalise_error("Recraft", exc) from exc

        data = payload.get("data") if isinstance(payload, dict) else None
        if not data:
            raise GeneratorError("Recraft returned no image data.", provider="Recraft")
        image_bytes = _read_image_payload(data[0])
        metadata: dict[str, Any] = {
            "variant": index + 1,
            "size": size,
        }
        if random_seed is not None:
            metadata["random_seed"] = int(random_seed) + index
        if isinstance(payload, dict) and payload.get("style_id"):
            metadata["style_id"] = payload["style_id"]

        images.append(
            GeneratedArtwork(
                image_bytes=image_bytes,
                prompt=variant_prompt,
                provider="Recraft",
                model=model,
                metadata=metadata,
            )
        )

    return images


def _google_image_block(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for step in payload.get("steps") or ():
        if not isinstance(step, dict):
            continue
        for block in step.get("content") or ():
            if (
                isinstance(block, dict)
                and block.get("type") == "image"
                and block.get("data")
            ):
                return str(block["data"])
    return ""


def generate_with_google(
    *,
    api_key: str,
    prompts: Sequence[str],
    model: str = "gemini-3.1-flash-image",
    size: str = "3:4",
) -> list[GeneratedArtwork]:
    """Generate raster artwork with the Gemini Interactions API."""

    if not api_key.strip():
        raise GeneratorError(
            "Connect Google Gemini with an API key before generating artwork.",
            provider="Google Gemini",
            code="missing_key",
        )
    _check_prompts(prompts)

    images: list[GeneratedArtwork] = []
    for index, variant_prompt in enumerate(prompts):
        body = {
            "model": model,
            "input": [{"type": "text", "text": variant_prompt}],
            "response_format": {
                "type": "image",
                "mime_type": "image/png",
                "aspect_ratio": size,
                "image_size": "2K",
            },
        }
        request = Request(
            GOOGLE_ENDPOINT,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "x-goog-api-key": api_key.strip(),
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=240) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")
            except OSError:
                detail = ""
            raise _normalise_error(
                "Google Gemini", exc, status_code=exc.code, details=detail
            ) from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise _normalise_error("Google Gemini", exc) from exc

        encoded = _google_image_block(payload)
        if not encoded:
            raise GeneratorError(
                "Google Gemini returned no image. It may have declined the description.",
                provider="Google Gemini",
                code="content",
            )
        image_bytes = _read_image_payload({"b64_json": encoded})

        images.append(
            GeneratedArtwork(
                image_bytes=image_bytes,
                prompt=variant_prompt,
                provider="Google Gemini",
                model=model,
                metadata={"variant": index + 1, "size": size},
            )
        )

    return images


def generate_with_provider(
    *,
    provider_id: str,
    api_key: str,
    prompts: Sequence[str],
    model: str,
    size: str,
    quality: str = "low",
    random_seed: int | None = None,
) -> list[GeneratedArtwork]:
    provider = provider_id.strip().lower()
    if provider == "openai":
        return generate_with_openai(
            api_key=api_key,
            prompts=prompts,
            model=model,
            size=size,
            quality=quality,
        )
    if provider == "recraft":
        return generate_with_recraft(
            api_key=api_key,
            prompts=prompts,
            model=model,
            size=size,
            random_seed=random_seed,
        )
    if provider == "google":
        return generate_with_google(
            api_key=api_key,
            prompts=prompts,
            model=model,
            size=size,
        )
    raise GeneratorError(
        f"Unsupported image provider: {provider_id}", code="unsupported_provider"
    )


def openai_input_fidelity(closeness: float) -> str:
    """Translate the stored closeness into the two settings OpenAI accepts.

    Every other provider takes a number here, so Doodle stores one. OpenAI
    takes a choice of two words, and rejects anything else outright: sending
    0.85 returns "Supported values are: 'high' and 'low'" and no picture.
    """

    return "high" if float(closeness) >= 0.5 else "low"


def refine_with_openai(
    *,
    api_key: str,
    image_bytes: bytes,
    prompt: str,
    model: str = "gpt-image-2",
    size: str = "1024x1536",
    quality: str = "medium",
    closeness: float = 0.85,
    mask_bytes: bytes | None = None,
) -> GeneratedArtwork:
    """Change an existing picture with the OpenAI image edit endpoint."""

    instruction = _check_instruction(prompt)
    if not api_key.strip():
        raise GeneratorError(
            "Connect OpenAI with an API key before changing artwork.",
            provider="OpenAI",
            code="missing_key",
        )

    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - incomplete installation only.
        raise GeneratorError(
            "The OpenAI Python package is not installed. Run pip install -r requirements.txt.",
            provider="OpenAI",
            code="edit_failed",
        ) from exc

    request_kwargs: dict[str, Any] = {
        "model": model,
        "image": ("doodle.png", BytesIO(image_bytes), "image/png"),
        "prompt": instruction,
        "size": size,
        "quality": quality,
        "input_fidelity": openai_input_fidelity(closeness),
    }
    if mask_bytes:
        request_kwargs["mask"] = ("mask.png", BytesIO(mask_bytes), "image/png")

    try:
        client = OpenAI(api_key=api_key.strip(), timeout=240.0, max_retries=2)
        result = client.images.edit(**request_kwargs)
        if not result.data:
            raise GeneratorError(
                "OpenAI returned no changed image.",
                provider="OpenAI",
                code="edit_failed",
            )
        payload = _read_image_payload(result.data[0])
    except GeneratorError:
        raise
    except Exception as exc:
        raise _normalise_error("OpenAI", exc) from exc

    return GeneratedArtwork(
        image_bytes=payload,
        prompt=instruction,
        provider="OpenAI",
        model=model,
        metadata={"instruction": instruction, "size": size, "quality": quality},
    )


def refine_with_google(
    *,
    api_key: str,
    image_bytes: bytes,
    prompt: str,
    model: str = "gemini-3.1-flash-image",
    size: str = "3:4",
) -> GeneratedArtwork:
    """Change an existing picture with the Gemini Interactions API.

    The same endpoint and models as generation; the input becomes a text block
    followed by the picture rather than a text block alone.
    """

    instruction = _check_instruction(prompt)
    if not api_key.strip():
        raise GeneratorError(
            "Connect Google Gemini with an API key before changing artwork.",
            provider="Google Gemini",
            code="missing_key",
        )

    body = {
        "model": model,
        "input": [
            {"type": "text", "text": instruction},
            {
                "type": "image",
                "mime_type": "image/png",
                "data": base64.b64encode(image_bytes).decode("ascii"),
            },
        ],
        "response_format": {
            "type": "image",
            "mime_type": "image/png",
            "aspect_ratio": size,
            "image_size": "2K",
        },
    }
    request = Request(
        GOOGLE_ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "x-goog-api-key": api_key.strip(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=240) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except OSError:
            detail = ""
        raise _normalise_error(
            "Google Gemini", exc, status_code=exc.code, details=detail
        ) from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise _normalise_error("Google Gemini", exc) from exc

    encoded = _google_image_block(payload)
    if not encoded:
        raise GeneratorError(
            "Google Gemini returned no changed image. It may have declined the instruction.",
            provider="Google Gemini",
            code="content",
        )

    return GeneratedArtwork(
        image_bytes=_read_image_payload({"b64_json": encoded}),
        prompt=instruction,
        provider="Google Gemini",
        model=model,
        metadata={"instruction": instruction, "size": size},
    )


def refine_with_recraft(
    *,
    api_key: str,
    image_bytes: bytes,
    prompt: str,
    model: str = "recraftv4_1",
    closeness: float = 0.85,
    random_seed: int | None = None,
) -> GeneratedArtwork:
    """Change an existing picture with Recraft's image-to-image endpoint."""

    instruction = _check_instruction(prompt)
    if not api_key.strip():
        raise GeneratorError(
            "Connect Recraft with an API token before changing artwork.",
            provider="Recraft",
            code="missing_key",
        )

    # Recraft's strength is the difference from the original, the inverse of
    # closeness: its own documentation calls 0 "almost identical".
    strength = round(max(0.0, min(1.0, 1.0 - closeness)), 3)
    fields = {
        "prompt": instruction,
        "strength": str(strength),
        "model": model,
        "n": "1",
        "response_format": "b64_json",
    }
    if random_seed is not None:
        fields["random_seed"] = str(int(random_seed))

    payload_bytes, content_type = _multipart_body(
        fields, {"image": ("doodle.png", image_bytes, "image/png")}
    )
    request = Request(
        RECRAFT_EDIT_ENDPOINT,
        data=payload_bytes,
        headers={
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": content_type,
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=240) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except OSError:
            detail = ""
        raise _normalise_error(
            "Recraft", exc, status_code=exc.code, details=detail
        ) from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise _normalise_error("Recraft", exc) from exc

    data = payload.get("data") if isinstance(payload, dict) else None
    if not data:
        raise GeneratorError(
            "Recraft returned no changed image.",
            provider="Recraft",
            code="edit_failed",
        )

    return GeneratedArtwork(
        image_bytes=_read_image_payload(data[0]),
        prompt=instruction,
        provider="Recraft",
        model=model,
        metadata={"instruction": instruction, "strength": strength},
    )


def refine_with_provider(
    *,
    provider_id: str,
    api_key: str,
    image_bytes: bytes,
    prompt: str,
    model: str,
    size: str,
    quality: str = "medium",
    mask_bytes: bytes | None = None,
    random_seed: int | None = None,
) -> GeneratedArtwork:
    # Imported here so providers.py never imports this module and the
    # dependency between them stays one-way.
    from .providers import PROVIDERS, get_provider

    provider = provider_id.strip().lower()
    if provider not in PROVIDERS:
        raise GeneratorError(
            f"Unsupported image provider: {provider_id}", code="unsupported_provider"
        )

    spec = get_provider(provider)
    if not spec.supports_edit:
        raise GeneratorError(
            f"{spec.label} cannot change an existing picture.",
            provider=spec.label,
            code="edit_unsupported",
        )

    if provider == "openai":
        return refine_with_openai(
            api_key=api_key,
            image_bytes=image_bytes,
            prompt=prompt,
            model=model,
            size=size,
            quality=quality,
            closeness=spec.edit_closeness,
            mask_bytes=mask_bytes,
        )
    if provider == "google":
        return refine_with_google(
            api_key=api_key,
            image_bytes=image_bytes,
            prompt=prompt,
            model=model,
            size=size,
        )
    return refine_with_recraft(
        api_key=api_key,
        image_bytes=image_bytes,
        prompt=prompt,
        model=model,
        closeness=spec.edit_closeness,
        random_seed=random_seed,
    )


def check_provider_connection(provider_id: str, api_key: str) -> dict[str, Any]:
    """Verify a credential without creating a paid image.

    OpenAI is checked against the models endpoint. A restricted key may block
    that endpoint while still permitting image generation, so HTTP 403 is
    treated as a recognised key with a warning rather than as an invalid key.
    Recraft exposes a dedicated user-information endpoint with the API balance.
    """

    provider = provider_id.strip().lower()
    key = api_key.strip()
    if not key:
        raise GeneratorError("Paste an API key first.", code="missing_key")

    if provider == "openai":
        endpoint = "https://api.openai.com/v1/models"
        label = "OpenAI"
    elif provider == "recraft":
        endpoint = "https://external.api.recraft.ai/v1/users/me"
        label = "Recraft"
    elif provider == "google":
        endpoint = "https://generativelanguage.googleapis.com/v1beta/models"
        label = "Google Gemini"
    else:
        raise GeneratorError(
            f"Unsupported image provider: {provider_id}", code="unsupported_provider"
        )

    # Google authenticates with its own header rather than a bearer token.
    headers = {"Accept": "application/json"}
    if provider == "google":
        headers["x-goog-api-key"] = key
    else:
        headers["Authorization"] = f"Bearer {key}"

    request = Request(endpoint, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
    except HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except OSError:
            detail = ""
        if provider == "openai" and exc.code == 403:
            return {
                "valid": True,
                "provider": label,
                "warning": "The key is recognised, but its restricted permissions prevented a full connection check.",
            }
        raise _normalise_error(
            label, exc, status_code=exc.code, details=detail
        ) from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise _normalise_error(label, exc) from exc

    result: dict[str, Any] = {"valid": True, "provider": label}
    if provider == "recraft" and isinstance(payload, dict):
        if "credits" in payload:
            result["credits"] = payload.get("credits")
        if payload.get("email"):
            result["account"] = payload.get("email")
    return result
