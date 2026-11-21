import pytest

from colouring_factory import wordsearch_words as ww
from colouring_factory.generators import GeneratorError

KW = dict(word_count=8, min_len=3, max_len=6)


def _no_model_call(*args, **kwargs):
    raise AssertionError("text model should not be called")


def test_every_built_in_topic_is_big_enough_and_lower_case() -> None:
    assert len(ww.BUILT_IN_TOPICS) >= 12
    for topic, words in ww.BUILT_IN_TOPICS.items():
        assert len(words) >= 20, topic
        assert all(w == w.lower() and w.isalpha() for w in words), topic


@pytest.mark.parametrize(
    "topic,expected",
    [
        ("Animals", "cat"),
        ("kitchen things", "spoon"),
        ("our family", "mum"),
        ("sea creatures", "crab"),
        ("fruits", "apple"),
        ("veg", "carrot"),
    ],
)
def test_built_in_topics_match_plurals_and_synonyms(topic, expected) -> None:
    words = ww.words_for_topic(topic, provider_id="recraft", api_key="", **KW)
    assert expected in words
    assert all(3 <= len(w) <= 6 for w in words)


def test_text_model_reply_is_filtered_by_letter_count(monkeypatch) -> None:
    monkeypatch.setattr(
        ww,
        "_openai_text",
        lambda model, key, instruction: (
            '["Cat", "fire engine", "elephant", "ox", "cat", "dog", "ice cream"]'
        ),
    )
    words = ww.words_for_topic(
        "things", provider_id="openai", api_key="k", word_count=5, min_len=3, max_len=8
    )
    # "fire engine" is 10 letters and "ox" 2; "ice cream" is 8 once spaces go.
    assert words == ["cat", "elephant", "dog", "ice cream"]


def test_google_provider_uses_the_google_helper(monkeypatch) -> None:
    monkeypatch.setattr(ww, "_openai_text", _no_model_call)
    monkeypatch.setattr(ww, "_google_text", lambda model, key, instruction: '["owl"]')
    assert ww.words_for_topic("birds", provider_id="google", api_key="k", **KW) == [
        "owl"
    ]


def test_text_model_failure_falls_back_to_built_in(monkeypatch) -> None:
    def boom(*args):
        raise OSError("offline")

    monkeypatch.setattr(ww, "_openai_text", boom)
    words = ww.words_for_topic("farm", provider_id="openai", api_key="k", **KW)
    assert "tractor" not in words  # 7 letters, over the limit
    assert "barn" in words


def test_unknown_topic_without_text_model_raises() -> None:
    with pytest.raises(GeneratorError) as caught:
        ww.words_for_topic("quantum physics", provider_id="recraft", api_key="", **KW)
    assert caught.value.code == "unknown_topic"
