import re

from .generators import GeneratorError
from .providers import get_provider
from .variations import _extract_json_array, _google_text, _openai_text

# British English, short familiar nouns a young child can picture and draw.
BUILT_IN_TOPICS: dict[str, tuple[str, ...]] = {
    "animal": (
        "cat",
        "dog",
        "pig",
        "cow",
        "hen",
        "fox",
        "bear",
        "lion",
        "tiger",
        "zebra",
        "monkey",
        "horse",
        "sheep",
        "goat",
        "duck",
        "frog",
        "mouse",
        "rabbit",
        "snake",
        "giraffe",
        "elephant",
        "hedgehog",
    ),
    "farm": (
        "cow",
        "pig",
        "hen",
        "duck",
        "sheep",
        "goat",
        "horse",
        "barn",
        "tractor",
        "farmer",
        "egg",
        "hay",
        "field",
        "gate",
        "chick",
        "lamb",
        "mud",
        "fence",
        "turkey",
        "donkey",
    ),
    "kitchen": (
        "cup",
        "plate",
        "bowl",
        "spoon",
        "fork",
        "knife",
        "pan",
        "pot",
        "kettle",
        "oven",
        "fridge",
        "sink",
        "tap",
        "jug",
        "mug",
        "toaster",
        "whisk",
        "apron",
        "table",
        "chair",
        "cooker",
    ),
    "family": (
        "mum",
        "dad",
        "baby",
        "sister",
        "brother",
        "nan",
        "grandad",
        "uncle",
        "aunt",
        "cousin",
        "twin",
        "granny",
        "grandma",
        "grandpa",
        "child",
        "home",
        "pet",
        "friend",
        "parent",
        "hug",
    ),
    "toy": (
        "ball",
        "doll",
        "kite",
        "drum",
        "bricks",
        "teddy",
        "robot",
        "train",
        "car",
        "puzzle",
        "yoyo",
        "top",
        "bat",
        "rattle",
        "balloon",
        "game",
        "blocks",
        "rocket",
        "bike",
        "slide",
    ),
    "food": (
        "bread",
        "cheese",
        "milk",
        "egg",
        "toast",
        "pizza",
        "pasta",
        "rice",
        "soup",
        "cake",
        "jam",
        "honey",
        "butter",
        "biscuit",
        "sausage",
        "chips",
        "pie",
        "cereal",
        "yoghurt",
        "sandwich",
    ),
    "fruit": (
        "apple",
        "pear",
        "plum",
        "peach",
        "banana",
        "grape",
        "lemon",
        "lime",
        "orange",
        "cherry",
        "melon",
        "mango",
        "kiwi",
        "berry",
        "fig",
        "date",
        "pineapple",
        "strawberry",
        "raspberry",
        "coconut",
    ),
    "vegetable": (
        "carrot",
        "potato",
        "pea",
        "bean",
        "onion",
        "leek",
        "corn",
        "cabbage",
        "lettuce",
        "tomato",
        "cucumber",
        "pepper",
        "radish",
        "turnip",
        "beetroot",
        "mushroom",
        "celery",
        "broccoli",
        "parsnip",
        "pumpkin",
    ),
    "sea": (
        "fish",
        "whale",
        "shark",
        "crab",
        "seal",
        "squid",
        "octopus",
        "starfish",
        "shell",
        "wave",
        "boat",
        "dolphin",
        "turtle",
        "jellyfish",
        "seahorse",
        "lobster",
        "anchor",
        "beach",
        "sand",
        "seaweed",
    ),
    "transport": (
        "car",
        "bus",
        "train",
        "bike",
        "boat",
        "ship",
        "plane",
        "van",
        "lorry",
        "tram",
        "taxi",
        "tractor",
        "rocket",
        "ferry",
        "scooter",
        "helicopter",
        "truck",
        "tube",
        "canoe",
        "cart",
    ),
    "clothes": (
        "hat",
        "coat",
        "shoe",
        "sock",
        "scarf",
        "glove",
        "boot",
        "shirt",
        "dress",
        "skirt",
        "jumper",
        "shorts",
        "trousers",
        "cap",
        "belt",
        "pyjamas",
        "vest",
        "tie",
        "jacket",
        "slipper",
    ),
    "garden": (
        "flower",
        "tree",
        "grass",
        "seed",
        "spade",
        "rake",
        "shed",
        "pond",
        "bee",
        "worm",
        "snail",
        "gate",
        "hose",
        "pot",
        "rose",
        "bush",
        "leaf",
        "fence",
        "wheelbarrow",
        "butterfly",
    ),
    "weather": (
        "sun",
        "rain",
        "snow",
        "wind",
        "cloud",
        "storm",
        "fog",
        "ice",
        "frost",
        "rainbow",
        "thunder",
        "lightning",
        "puddle",
        "hail",
        "breeze",
        "sky",
        "umbrella",
        "mist",
        "flood",
        "drizzle",
    ),
}

_SYNONYMS = {
    "creature": "animal",
    "pet": "animal",
    "zoo": "animal",
    "mammal": "animal",
    "bird": "farm",
    "farmyard": "farm",
    "cooking": "kitchen",
    "cook": "kitchen",
    "relative": "family",
    "relation": "family",
    "plaything": "toy",
    "meal": "food",
    "snack": "food",
    "veg": "vegetable",
    "veggie": "vegetable",
    "ocean": "sea",
    "beach": "sea",
    "seaside": "sea",
    "vehicle": "transport",
    "travel": "transport",
    "clothing": "clothes",
    "outfit": "clothes",
    "plant": "garden",
}

_INSTRUCTION = (
    "List {count} words for a children's word search on the topic: {topic}.\n"
    "Each must be a concrete, picturable noun that a young child knows, in "
    "lower case, a single word or a short phrase, with between {min_len} and "
    "{max_len} letters (not counting spaces). No duplicates.\n"
    "Reply with only a JSON array of strings."
)


def _singular(word: str) -> str:
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("es") and word[:-2].endswith(("s", "x", "ch", "sh")):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _built_in_key(topic: str) -> str | None:
    # Whole phrase first, then each word, so "sea creatures" and "our family"
    # find their lists without every phrasing being spelled out.
    tokens = re.findall(r"[a-z]+", topic.lower())
    for candidate in (" ".join(tokens), *tokens):
        for form in (candidate, _singular(candidate)):
            if form in BUILT_IN_TOPICS:
                return form
            if form in _SYNONYMS:
                return _SYNONYMS[form]
    return None


def _clean(words, *, min_len: int, max_len: int) -> list[str]:
    kept: list[str] = []
    seen: set[str] = set()
    for raw in words:
        word = re.sub(r"\s+", " ", str(raw).strip().lower())
        squashed = word.replace(" ", "")
        if not squashed.isalpha() or not min_len <= len(squashed) <= max_len:
            continue
        if squashed in seen:
            continue
        seen.add(squashed)
        kept.append(word)
    return kept


def _ask_text_model(
    topic: str, count: int, min_len: int, max_len: int, provider_id: str, api_key: str
) -> list[str]:
    spec = get_provider(provider_id)
    if not spec.text_model or not api_key.strip():
        raise GeneratorError(f"{spec.label} has no text model.", code="no_text_model")
    instruction = _INSTRUCTION.format(
        count=count, topic=topic, min_len=min_len, max_len=max_len
    )
    if spec.id == "google":
        reply = _google_text(spec.text_model, api_key.strip(), instruction)
    else:
        reply = _openai_text(spec.text_model, api_key.strip(), instruction)
    return _extract_json_array(reply)


def words_for_topic(
    topic: str,
    *,
    word_count: int,
    min_len: int,
    max_len: int,
    provider_id: str,
    api_key: str,
) -> list[str]:
    topic = topic.strip()
    words: list[str] = []
    try:
        # Spares, because the model's words are filtered and may repeat.
        candidates = _ask_text_model(
            topic, word_count + 4, min_len, max_len, provider_id, api_key
        )
        words = _clean(candidates, min_len=min_len, max_len=max_len)
    except Exception:
        # Any provider failure still leaves the built-in lists to fall back on.
        words = []
    if words:
        return words

    key = _built_in_key(topic)
    if key:
        words = _clean(BUILT_IN_TOPICS[key], min_len=min_len, max_len=max_len)
    if not words:
        raise GeneratorError(
            f'Doodle has no words for "{topic}". Type your own words instead.',
            code="unknown_topic",
        )
    return words


TITLE_LIMIT = 28

_TITLE_INSTRUCTION = (
    "Write a short, cheerful title for a children's word search printed at "
    "the top of the page. {about}\n"
    "At most {limit} characters and four words, British English, no quotation "
    "marks, no emoji, no full stop. Reply with only the title."
)


def _tidy_title(raw: str) -> str:
    title = " ".join(str(raw).strip().strip("\"'“”‘’.").split())
    return title[:1].upper() + title[1:]


def _short_fallback(text: str) -> str:
    # Whole words up to the limit, so a long typed topic never becomes a
    # title that runs off the page even when no model is reachable.
    kept: list[str] = []
    for word in text.split():
        if len(" ".join([*kept, word])) > TITLE_LIMIT:
            break
        kept.append(word)
    return _tidy_title(" ".join(kept)) if kept else ""


def title_for_sheet(
    *,
    topic: str = "",
    words: list[str] | tuple[str, ...] = (),
    provider_id: str,
    api_key: str,
) -> str:
    """A short title for the sheet, from the topic or the words on it.

    The connected provider's small text model writes it; if that fails, or
    its answer is too long, the topic itself is shortened instead.
    """

    if topic.strip():
        about = f"The topic is: {topic.strip()}."
    else:
        about = "The words to find are: " + ", ".join(words) + "."
    fallback = _short_fallback(topic) or "Find these words"
    spec = get_provider(provider_id)
    if not spec.text_model or not api_key.strip():
        return fallback
    instruction = _TITLE_INSTRUCTION.format(about=about, limit=TITLE_LIMIT)
    try:
        if spec.id == "google":
            reply = _google_text(spec.text_model, api_key.strip(), instruction)
        else:
            reply = _openai_text(spec.text_model, api_key.strip(), instruction)
    except Exception:
        return fallback
    title = _tidy_title(reply.splitlines()[0] if reply.strip() else "")
    if not title or len(title) > TITLE_LIMIT:
        return fallback
    return title
