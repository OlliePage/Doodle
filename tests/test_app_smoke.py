from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest


class _StopExecution(Exception):
    pass


class _Context:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __getattr__(self, _name):
        return lambda *_args, **_kwargs: None


class _SessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


class _FakeStreamlit(types.ModuleType):
    def __init__(self, radio_overrides=None):
        super().__init__("streamlit")
        self.session_state = _SessionState()
        self.sidebar = _Context()
        self.radio_overrides = radio_overrides or {}
        self.markdown_calls = []
        self.text_input_calls = []

    def cache_data(self, func=None, **_kwargs):
        if func is not None:
            return func

        def decorator(inner):
            return inner

        return decorator

    def tabs(self, labels):
        return [_Context() for _ in labels]

    def columns(self, spec):
        count = spec if isinstance(spec, int) else len(spec)
        return [_Context() for _ in range(count)]

    def form(self, *_args, **_kwargs):
        return _Context()

    def container(self, *_args, **_kwargs):
        return _Context()

    def expander(self, *_args, **_kwargs):
        return _Context()

    def popover(self, *_args, **_kwargs):
        return _Context()

    def spinner(self, *_args, **_kwargs):
        return _Context()

    def radio(self, label, options, **_kwargs):
        return self.radio_overrides.get(label, list(options)[0])

    def selectbox(self, _label, options, index=0, **_kwargs):
        return list(options)[index]

    def segmented_control(self, label, options, default=None, **_kwargs):
        if label in self.radio_overrides:
            return self.radio_overrides[label]
        return default if default is not None else list(options)[0]

    def select_slider(self, _label, options, value=None, **_kwargs):
        return value if value is not None else list(options)[0]

    def text_input(self, label, value="", **kwargs):
        self.text_input_calls.append((label, kwargs))
        key = kwargs.get("key")
        if key and key in self.session_state:
            return self.session_state[key]
        return value

    def text_area(self, _label, value="", **_kwargs):
        return value

    def number_input(self, _label, *args, value=None, **_kwargs):
        if value is not None:
            return value
        # Streamlit positional order after label is min, max, value, step.
        return args[2] if len(args) >= 3 else 0

    def slider(self, _label, *args, value=None, **_kwargs):
        if value is not None:
            return value
        return args[2] if len(args) >= 3 else 0

    def checkbox(self, _label, value=False, **_kwargs):
        return value

    def file_uploader(self, *_args, **_kwargs):
        return None

    def button(self, *_args, **_kwargs):
        return False

    def form_submit_button(self, *_args, **_kwargs):
        return False

    def download_button(self, *_args, **_kwargs):
        return False

    def rerun(self, *_args, **_kwargs):
        return None

    def stop(self):
        raise _StopExecution

    def markdown(self, body, **_kwargs):
        self.markdown_calls.append(body)
        return None

    def __getattr__(self, _name):
        # Display calls such as title, image, metric, markdown and caption.
        return lambda *_args, **_kwargs: None


def _execute_app(
    monkeypatch, tmp_path, layout_choice: str, module_suffix: str, **widget_choices
):
    fake = _FakeStreamlit({"Output format": layout_choice, **widget_choices})
    project_root = Path(__file__).resolve().parents[1]
    fake.session_state["current_raw"] = (
        project_root / "assets" / "demo_dinosaur.png"
    ).read_bytes()
    fake.session_state["current_title"] = "Smoke-test dinosaur"
    fake.session_state["current_metadata"] = {"source": "test"}
    monkeypatch.setitem(sys.modules, "streamlit", fake)
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / module_suffix / "data"))

    app_path = project_root / "app.py"
    spec = importlib.util.spec_from_file_location(
        f"colouring_factory_app_{module_suffix}", app_path
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return fake


def test_fresh_app_opens_on_minimal_doodle_homepage(monkeypatch, tmp_path) -> None:
    fake = _FakeStreamlit()
    project_root = Path(__file__).resolve().parents[1]
    monkeypatch.setitem(sys.modules, "streamlit", fake)
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "home" / "data"))

    app_path = project_root / "app.py"
    spec = importlib.util.spec_from_file_location("doodle_app_home", app_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)

    with pytest.raises(_StopExecution):
        spec.loader.exec_module(module)

    assert any("doodle-logo--hero" in body for body in fake.markdown_calls)

    assert len(fake.text_input_calls) == 1
    label, kwargs = fake.text_input_calls[0]
    assert label == "Describe a picture to colour"
    assert kwargs["key"] == "home_prompt"
    assert kwargs["placeholder"] == "What shall we draw?"
    assert kwargs["label_visibility"] == "collapsed"
    # No on_change: it fires when the box loses focus, which sent a half-typed
    # prompt to the next screen. Submission goes through the form instead.
    assert "on_change" not in kwargs

    # Submitting an idea must leave the homepage. Which screen it goes to
    # depends on whether a provider key is present, so assert only that it moved.
    fake.session_state["home_prompt"] = "A bear flying a kite"
    module._submit_home_prompt()
    assert fake.session_state["screen"] != "home"
    assert fake.session_state["generation_idea"] == "A bear flying a kite"


def test_streamlit_app_executes_full_page_branch(monkeypatch, tmp_path) -> None:
    fake = _execute_app(monkeypatch, tmp_path, "A4 colouring page", "full")
    assert fake.session_state["current_raw"] is not None


def test_streamlit_app_executes_circle_branch(monkeypatch, tmp_path) -> None:
    fake = _execute_app(monkeypatch, tmp_path, "A4 circle sheet", "circle")
    assert fake.session_state["current_raw"] is not None


def test_the_circle_branch_defaults_to_fitting_the_whole_picture(
    monkeypatch, tmp_path
) -> None:
    # The badge preview runs for real inside this branch, so reaching the end
    # of the script proves the preview renders with the default settings.
    fake = _execute_app(monkeypatch, tmp_path, "A4 circle sheet", "circle_inscribe")
    assert fake.session_state["current_raw"] is not None


def test_the_circle_branch_accepts_filling_the_circle(monkeypatch, tmp_path) -> None:
    fake = _execute_app(
        monkeypatch,
        tmp_path,
        "A4 circle sheet",
        "circle_fill",
        **{"Artwork fit": "Fill the circle"},
    )
    assert fake.session_state["current_raw"] is not None


def test_streamlit_app_executes_custom_branch(monkeypatch, tmp_path) -> None:
    fake = _execute_app(monkeypatch, tmp_path, "Custom-size page", "custom")
    assert fake.session_state["current_raw"] is not None
