from __future__ import annotations

VARIATION_AXES: dict[str, tuple[str, ...]] = {
    "moment": (
        "the busiest moment of the action",
        "the quiet moment just before it begins",
        "the moment just after it is finished",
        "an unexpected small mishap in the middle of it",
    ),
    "framing": (
        "a wide view showing the whole scene",
        "a close view of the main character's face and hands",
        "a low view looking up at the subject",
        "a side view showing the whole body in profile",
    ),
    "setting": (
        "outdoors on a sunny day",
        "indoors in a cosy room",
        "in a garden with simple large plants",
        "beside water, with simple wide ripples",
    ),
    "mood": (
        "cheerful and energetic",
        "calm and sleepy",
        "proud and pleased",
        "surprised and curious",
    ),
}

_AXIS_ORDER = ("moment", "framing", "setting", "mood")


def axis_briefs(concept: str, count: int) -> tuple[str, ...]:
    """Compose distinct scene briefs by varying four axes independently.

    Each axis advances by a different stride so that four briefs never repeat a
    combination, and a request for fewer alternatives is a prefix of a request
    for more — pressing "another" must not reshuffle pictures already seen.
    """

    concept = concept.strip()
    if not concept:
        raise ValueError("A picture idea is required.")
    if count < 1 or count > 4:
        raise ValueError("Between one and four alternatives can be produced.")

    strides = (1, 3, 2, 3)
    offset = sum(ord(character) for character in concept)

    briefs: list[str] = []
    for index in range(count):
        parts = []
        for axis_position, axis_name in enumerate(_AXIS_ORDER):
            values = VARIATION_AXES[axis_name]
            chosen = values[(offset + (index * strides[axis_position])) % len(values)]
            parts.append(chosen)
        moment, framing, setting, mood = parts
        briefs.append(
            f"{concept}, showing {moment}, drawn as {framing}, {setting}, feeling {mood}."
        )
    return tuple(briefs)
