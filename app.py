from __future__ import annotations

import html
import hashlib
import json
import re
import time
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime

import streamlit as st

from colouring_factory.appearance import describe_appearance
from colouring_factory.badge_preview import render_badge_preview
from colouring_factory.browser_print import print_trigger_html
from colouring_factory.calibration import profile_from_measurements
from colouring_factory.characters import (
    CHARACTER_KINDS,
    Character,
    character_portrait_mtime,
    characters_signature,
    delete_character,
    list_characters,
    load_character_image,
    load_character_portrait,
    resolve_cast,
    save_character,
    toggle_chosen,
    update_character,
    update_character_portrait,
)
from colouring_factory.demo import list_demo_artwork
from colouring_factory.credentials import (
    delete_provider_key,
    mask_key,
    resolve_provider_key,
    save_provider_key,
)
from colouring_factory.generators import (
    GeneratorError,
    check_provider_connection,
    generate_with_provider,
    refine_with_provider,
)
from colouring_factory import history
from colouring_factory.guidance import guidance_for
from colouring_factory.timings import (
    MIN_RECORDS_FOR_CHART,
    bar_heights,
    durations_for,
    histogram,
    load_timings,
    record_timing,
    settings_key,
)
from colouring_factory.version import build_label
from colouring_factory.image_processing import analyse_line_art, normalise_line_art
from colouring_factory.layouts import (
    compute_circle_sheet_plan,
    largest_margin_that_fits,
)
from colouring_factory.models import (
    CalibrationProfile,
    CircleSheetConfig,
    CustomPageConfig,
    FullPageConfig,
    GeneratedArtwork,
    ProcessingOptions,
)
from colouring_factory.pdf_export import (
    create_calibration_pdf,
    create_circle_sheet_pdf,
    create_custom_page_pdf,
    create_full_page_pdf,
)
from colouring_factory.photos import MAX_ARTWORK_EDGE_PX, prepare_photo
from colouring_factory.preview import render_pdf_preview
from colouring_factory.providers import (
    DEFAULT_PROVIDER,
    PROVIDERS,
    get_provider,
    provider_id_from_label,
)
from colouring_factory.prompts import (
    STYLE_PRESETS,
    build_caricature_prompt,
    build_character_scene_prompt,
    build_colouring_prompt,
    build_colour_suggestion_prompt,
    build_refinement_prompt,
)
from colouring_factory.variations import build_variation_briefs, split_pairing_results
from colouring_factory.storage import (
    GROWN_UP_LEVEL,
    QUICK_AGE_CHOICES,
    QUICK_ALTERNATIVE_CHOICES,
    QUICK_STYLE_CHOICES,
    data_root,
    delete_library_item,
    list_library_items,
    load_library_image,
    load_settings,
    quick_drawing_options,
    save_library_item,
    save_settings,
)

# Low quality renders fine detail such as a hat brim in pale grey that the
# black/white pass then breaks into a dotted line. Medium produces fewer of
# those strokes in the first place.
DEFAULT_QUALITY = "medium"


def _drawing_already_in_flight(flag_key: str) -> bool:
    """Whether a paid call under this key is already running.

    Streamlit can queue a click made while that same control's previous
    press is still blocked in a network call, and replay it the moment the
    call returns — which used to buy a second picture from one press.
    Callers check this before starting work and skip the click outright
    when it is already true.
    """

    return bool(st.session_state.get(flag_key))


@contextmanager
def _mark_in_flight(flag_key: str):
    """Flags a paid call as running for the width of the call.

    Always cleared on the way out, success or exception, so a call that
    fails leaves its control pressable again rather than wedged shut for
    the rest of the session.
    """

    st.session_state[flag_key] = True
    try:
        yield
    finally:
        st.session_state[flag_key] = False


st.set_page_config(
    page_title="Doodle",
    page_icon="✏️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      :root {
        --doodle-ink: #171717;
        --doodle-muted: #676b70;
        --doodle-line: #e1e4e8;
        --doodle-soft: #f7f7f8;
        --doodle-primary: #4f46e5;
      }

      #MainMenu, footer {visibility: hidden;}
      [data-testid="stDecoration"] {display: none;}
      .block-container,
      [data-testid="stMainBlockContainer"] {
        max-width: 1180px;
        padding-top: 5rem;
        padding-bottom: 3rem;
        overflow: visible;
      }
      [data-testid="stSidebar"] .block-container {padding-top: 2rem;}
      .small-muted {color: var(--doodle-muted); font-size: 0.88rem;}
      .step-label {
        font-weight: 760;
        letter-spacing: .055em;
        text-transform: uppercase;
        font-size: .73rem;
        color: #73777d;
        margin-top: .6rem;
      }
      .geometry-box {
        border: 1px solid var(--doodle-line);
        border-radius: 1rem;
        padding: .9rem 1rem;
        margin-top: .6rem;
        background: #fff;
      }
      .studio-subtitle {
        color: var(--doodle-muted);
        font-size: .98rem;
        margin: .1rem 0 1.25rem;
      }
      .doodle-logo {
        position: relative;
        display: table;
        overflow: visible;
        color: var(--doodle-ink);
        font-family: "Arial Rounded MT Bold", "Trebuchet MS", "Avenir Next", sans-serif;
        font-weight: 900;
        line-height: 1.08;
        letter-spacing: -.105em;
        white-space: nowrap;
        user-select: none;
        padding: .12em .04em .08em 0;
      }
      .doodle-logo--hero {
        margin: 0 auto 2.35rem;
        font-size: clamp(4.9rem, 12vw, 8.15rem);
        padding-right: .16em;
      }
      .doodle-logo--compact {
        margin: 0 0 .25rem;
        font-size: 2.35rem;
        padding-right: .16em;
      }
      .doodle-logo--centred {
        margin-left: auto;
        margin-right: auto;
      }
      .doodle-letter {
        position: relative;
        display: inline-block;
        -webkit-text-stroke: .012em rgba(20, 20, 20, .13);
        text-shadow: 0 .035em 0 rgba(20, 20, 20, .08);
      }
      .doodle-letter--1 {color: #4f46e5; transform: rotate(-4deg) translateY(.01em);}
      .doodle-letter--2 {color: #f45b69; transform: rotate(3deg) translateY(-.025em);}
      .doodle-letter--3 {color: #f5a623; transform: rotate(-2deg) translateY(.018em);}
      .doodle-letter--4 {color: #16a085; transform: rotate(3deg) translateY(-.005em);}
      .doodle-letter--5 {color: #8b5cf6; transform: rotate(-3deg) translateY(.025em);}
      .doodle-letter--6 {color: #0ea5e9; transform: rotate(2deg) translateY(-.018em);}
      .doodle-logo__spark {
        position: absolute;
        right: -.08em;
        top: -.12em;
        color: #f5a623;
        font-family: Georgia, serif;
        font-size: .22em;
        letter-spacing: 0;
        transform: rotate(12deg);
      }
      .doodle-logo--hero::after {
        content: "";
        display: block;
        width: 73%;
        height: .11em;
        margin: .1em auto 0;
        border-top: .055em solid #202124;
        border-radius: 50%;
        transform: rotate(-1.5deg);
      }
      div[data-testid="stButton"] > button,
      div[data-testid="stDownloadButton"] > button,
      div[data-testid="stLinkButton"] > a {
        min-height: 2.75rem;
        border-radius: 999px;
      }
      div[data-testid="stButton"] > button:focus-visible,
      div[data-testid="stDownloadButton"] > button:focus-visible,
      div[data-testid="stLinkButton"] > a:focus-visible {
        outline: 3px solid rgba(79, 70, 229, .24);
        outline-offset: 2px;
      }
      .stTabs [data-baseweb="tab-list"] {gap: .35rem;}
      .stTabs [data-baseweb="tab"] {border-radius: 999px; padding-left: 1rem; padding-right: 1rem;}
      .stTabs [aria-selected="true"] {background: var(--doodle-soft);}
      @media (max-width: 640px) {
        .block-container, [data-testid="stMainBlockContainer"] {
          padding-top: 2rem;
          padding-left: 1rem;
          padding-right: 1rem;
        }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# Rendered here rather than at the end of the script: three st.stop() calls
# below mean the end is often never reached. Fixed positioning makes the
# element's place in the document irrelevant to where it appears.
st.html(
    f"""
    <style>
      /* Selectable on purpose. The badge exists so two people can confirm
         they are running the same code, which means reading it out is not
         enough — it has to be copyable. One click takes the whole label. */
      .doodle-build {{
        position: fixed;
        right: .4rem;
        bottom: .15rem;
        z-index: 1000;
        padding: .35rem .5rem;
        font-size: .7rem;
        font-variant-numeric: tabular-nums;
        color: var(--doodle-muted, #676b70);
        opacity: .55;
        cursor: text;
        -webkit-user-select: all;
        user-select: all;
        transition: opacity .15s ease;
      }}
      .doodle-build:hover {{
        opacity: 1;
      }}
    </style>
    <div class="doodle-build">{build_label()}</div>
    """
)


def _doodle_logo(mode: str = "compact", *, centred: bool = False) -> str:
    centred_class = " doodle-logo--centred" if centred else ""
    return f"""
    <div class="doodle-logo doodle-logo--{mode}{centred_class}" aria-label="Doodle">
      <span class="doodle-letter doodle-letter--1">D</span>
      <span class="doodle-letter doodle-letter--2">o</span>
      <span class="doodle-letter doodle-letter--3">o</span>
      <span class="doodle-letter doodle-letter--4">d</span>
      <span class="doodle-letter doodle-letter--5">l</span>
      <span class="doodle-letter doodle-letter--6">e</span>
      <span class="doodle-logo__spark">✦</span>
    </div>
    """


def _initialise_state() -> None:
    defaults = {
        "screen": "home",
        "home_prompt": "",
        "home_error": "",
        "home_error_code": "",
        "generation_idea": "",
        "candidates": [],
        "current_raw": None,
        "current_metadata": {},
        "current_title": "",
        "pdf_bytes": None,
        "pdf_filename": "doodle.pdf",
        "pdf_summary": "",
        "pdf_signature": "",
        "library_notice": "",
        "character_notice": "",
        "character_duplicate_notice": "",
        "library_return": "home",
        "pending_delete": "",
        # The picker's ticks live here rather than in per-character widget keys.
        # Streamlit garbage-collects a widget key the moment its widget is not
        # rendered, so ticking someone, visiting this screen and coming back
        # would silently lose every tick.
        "chosen_characters": [],
        "pending_character_delete": "",
        "quick_processed": None,
        "quick_pdf": None,
        "quick_saved": False,
        "pair_raw": None,
        "pair_processed": None,
        "pair_pdf": None,
        "badge_previews": {},
        "colour_previews": {},
        "showing_colours": False,
        "session_provider_keys": {},
        "provider_choice": DEFAULT_PROVIDER,
        "connect_return": "generate",
        "connect_replace": False,
        "connection_error": None,
        "pending_remember_key": True,
        "pending_provider": "",
        "quick_mode": "ai",
        "generation_nonce": 0,
        # A batch in progress on the generate screen: which pictures remain
        # to be drawn, and what has been drawn of them so far. Reset to
        # empty whenever a batch finishes, is stopped, or fails — see
        # _clear_generation_plan — so a fresh visit never continues a stale
        # one left over from an earlier idea.
        "generation_jobs": [],
        "generation_collected": [],
        "generation_uses_cast": False,
        "generation_references": (),
        "generation_chosen_ids": [],
        "generation_pairing": False,
        "generation_random_seed_base": 0,
        "generation_stop_requested": False,
        # Read and cleared at the top of the result screen: a failure that
        # still kept what had already been drawn (unlike a stop, which the
        # parent already knows they pressed) needs to say what happened.
        "generation_notice": "",
        "doodle_versions": (),
        "current_version": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # Upgrade sessions created by the earlier boolean-based prototype.
    if st.session_state.get("studio_open") and st.session_state.get("screen") == "home":
        st.session_state.screen = "studio"


_initialise_state()


def _active_provider_id() -> str:
    configured = str(load_settings().get("image_provider", DEFAULT_PROVIDER)).lower()
    return configured if configured in PROVIDERS else DEFAULT_PROVIDER


def _set_active_provider(provider_id: str) -> None:
    provider = provider_id if provider_id in PROVIDERS else DEFAULT_PROVIDER
    settings = load_settings()
    settings["image_provider"] = provider
    save_settings(settings)
    st.session_state.provider_choice = provider


def _provider_key(provider_id: str | None = None) -> tuple[str, str]:
    provider = provider_id or _active_provider_id()
    session_keys = st.session_state.get("session_provider_keys", {})
    return resolve_provider_key(provider, session_keys)


def _model_for(provider_id: str, spec, settings: dict) -> str:
    """Resolve the saved model choice, falling back when it is unset or stale.

    Was three copies of the same two lines, each of which a fourth generation
    site would otherwise have repeated a fourth time.
    """

    model = str(settings.get(f"{provider_id}_model", spec.default_model))
    return model if model in spec.models else spec.default_model


def _submit_home_prompt() -> None:
    prompt = str(st.session_state.get("home_prompt", "")).strip()
    if not prompt:
        return
    st.session_state.generation_idea = prompt
    st.session_state.home_error = ""
    st.session_state.home_error_code = ""
    st.session_state.connection_error = None
    st.session_state.connect_return = "generate"
    st.session_state.connect_replace = False
    st.session_state.quick_mode = "ai"
    st.session_state.generation_nonce = 0
    # A batch left behind by a stopped or finished earlier drawing must not
    # be picked back up as though it belonged to this new idea.
    _clear_generation_plan()
    api_key, _source = _provider_key()
    st.session_state.screen = "generate" if api_key else "connect"


def _start_new_doodle() -> None:
    st.session_state.screen = "home"
    st.session_state.home_prompt = ""
    st.session_state.home_error = ""
    st.session_state.home_error_code = ""
    st.session_state.generation_idea = ""
    st.session_state.candidates = []
    st.session_state.current_raw = None
    st.session_state.current_metadata = {}
    st.session_state.current_title = ""
    st.session_state.pdf_bytes = None
    st.session_state.pdf_summary = ""
    st.session_state.pdf_signature = ""
    st.session_state.quick_processed = None
    st.session_state.quick_pdf = None
    st.session_state.quick_saved = False
    st.session_state.pair_raw = None
    st.session_state.pair_processed = None
    st.session_state.pair_pdf = None
    # badge_previews is deliberately left alone, the same rule colour_previews
    # already follows: both are content-addressed caches, so an entry for a
    # picture no longer on screen is just unused, never wrong.
    st.session_state.showing_colours = False
    st.session_state.connection_error = None
    st.session_state.quick_mode = "ai"
    st.session_state.generation_nonce = 0
    _clear_generation_plan()
    # A chain left behind points the change box at the previous picture, so a
    # refinement quietly edits a doodle that is no longer on screen.
    st.session_state.doodle_versions = ()
    st.session_state.current_version = 0
    # chosen_characters is deliberately left alone: a parent drawing for the
    # same children wants the same cast next time, the same reasoning the
    # homepage settings already follow.
    st.rerun()


def _render_homepage() -> None:
    st.markdown(
        """
        <style>
          [data-testid="stHeader"],
          [data-testid="stToolbar"],
          [data-testid="collapsedControl"],
          [data-testid="stSidebar"] {display: none !important;}
          [data-testid="stAppViewContainer"],
          [data-testid="stApp"] {background: #fff;}
          .block-container,
          [data-testid="stMainBlockContainer"] {
            max-width: 860px !important;
            min-height: 100dvh;
            padding: clamp(3rem, 9vh, 6.5rem) 1.35rem clamp(5rem, 13vh, 8rem) !important;
            display: flex;
            flex-direction: column;
            justify-content: center;
            overflow: visible !important;
          }
          div[data-testid="stTextInput"] {
            width: min(100%, 730px);
            margin: 0 auto;
          }
          div[data-testid="stTextInput"] > div > div {
            min-height: 64px;
            border-radius: 999px !important;
            border: 1px solid #dfe1e5 !important;
            background: #fff !important;
            box-shadow: 0 1px 6px rgba(32, 33, 36, .20);
            transition: box-shadow .16s ease, border-color .16s ease;
            overflow: hidden;
          }
          div[data-testid="stTextInput"] > div > div:hover,
          div[data-testid="stTextInput"] > div > div:focus-within {
            border-color: transparent !important;
            box-shadow: 0 2px 10px rgba(32, 33, 36, .24);
          }
          div[data-testid="stTextInput"] input {
            height: 62px;
            padding: 0 1.7rem !important;
            border-radius: 999px;
            font-size: 1.08rem;
            color: #202124;
            caret-color: var(--doodle-primary);
          }
          div[data-testid="stTextInput"] input::placeholder {color: #858a91; opacity: 1;}
          /* Streamlit right-aligns its "Press Enter to apply" hint and clear
             button inside the input, where this 62px pill leaves no room, so
             they overlap each other and the rounded edge. Hidden here; the
             Draw it button below the bar cannot collide with anything. */
          div[data-testid="stTextInput"] [data-testid="InputInstructions"],
          div[data-testid="stTextInput"] button {display: none !important;}
          div[data-testid="stFormSubmitButton"] {
            width: min(100%, 730px);
            margin: .95rem auto 0;
          }
          div[data-testid="stFormSubmitButton"] button {
            border-radius: 999px;
            min-height: 48px;
            font-size: 1rem;
          }
          /* The route to saved doodles leaves the centre column entirely and
             takes the corner, the way a homepage keeps its account and inbox
             links out of the way of the search bar. Fixed, so it stays put
             while the column below it is vertically centred. */
          .st-key-doodle-home-corner {
            position: fixed;
            top: .7rem;
            right: 1.3rem;
            z-index: 20;
          }
          /* The settings read as one line of small grey text under the button.
             Each value opens its choices in a floating panel, so nothing on
             this page is a form and nothing reflows when it is opened. */
          .st-key-doodle-home-settings {
            margin-top: .85rem;
          }
          /* Streamlit truncates a button's label with an ellipsis, which on a
             one-word setting leaves "toddler bo…" and defeats the point of a
             line that is supposed to be readable at a glance. The wrappers
             are sized from the truncated label, so they have to be widened
             along with it. */
          .st-key-doodle-home-settings [data-testid="stLayoutWrapper"],
          .st-key-doodle-home-settings [data-testid="stPopover"],
          .st-key-doodle-home-settings [data-testid="stPopoverButton"],
          .st-key-doodle-home-settings [data-testid="stPopoverButton"] > div,
          .st-key-doodle-home-settings [data-testid="stPopoverButton"] > div > div {
            width: max-content !important;
            max-width: none !important;
            flex: 0 0 auto !important;
          }
          .st-key-doodle-home-settings [data-testid="stPopoverButton"] p {
            overflow: visible;
            text-overflow: clip;
            max-width: none;
            white-space: nowrap;
            margin: 0;
          }
          .st-key-doodle-home-corner button,
          .st-key-doodle-home-settings button {
            color: #5f6368 !important;
            font-size: .92rem;
            font-weight: 400;
            border-radius: 999px;
            padding: .25rem .7rem;
            min-height: 0;
          }
          .st-key-doodle-home-corner button:hover,
          .st-key-doodle-home-settings button:hover {
            background: #f4f5f7 !important;
            color: #202124 !important;
          }
          @media (max-width: 640px) {
            .block-container, [data-testid="stMainBlockContainer"] {
              padding: max(2.5rem, env(safe-area-inset-top)) 1rem max(4rem, env(safe-area-inset-bottom)) !important;
            }
            .doodle-logo--hero {font-size: clamp(4.1rem, 22vw, 6rem); margin-bottom: 1.9rem;}
            div[data-testid="stTextInput"] > div > div {min-height: 58px;}
            div[data-testid="stTextInput"] input {height: 56px; font-size: 1rem; padding: 0 1.3rem !important;}
          }
        </style>
        """,
        unsafe_allow_html=True,
    )
    # Offered only once there is something to open, so a first-time homepage
    # is a logo, a bar and a button and nothing else.
    saved_count = _saved_doodle_count()
    if saved_count:
        with st.container(
            key="doodle-home-corner", horizontal=True, horizontal_alignment="right"
        ):
            if st.button(
                f"Saved doodles ({saved_count})",
                type="tertiary",
                key="home_saved_link",
            ):
                st.session_state.library_return = "home"
                st.session_state.screen = "library"
                st.rerun()

    st.markdown(_doodle_logo("hero", centred=True), unsafe_allow_html=True)
    # A form, not on_change: a bare text input commits when it loses focus as
    # well as on Enter, so clicking away from a half-typed prompt jumped
    # straight to the next screen. A form commits only on Enter or the button.
    with st.form("home_prompt_form", border=False, clear_on_submit=False):
        st.text_input(
            "Describe a picture to colour",
            key="home_prompt",
            placeholder="What shall we draw?",
            label_visibility="collapsed",
        )
        home_submitted = st.form_submit_button(
            "Draw it", type="primary", width="stretch"
        )
    if home_submitted:
        _submit_home_prompt()
        if st.session_state.screen != "home":
            st.rerun()
    if st.session_state.get("home_error"):
        code = str(st.session_state.get("home_error_code") or "")
        if code:
            # A code carries the named control that owns the fix, not just
            # the bare failure message: "Untick some characters and draw
            # again," rather than a sentence naming no provider at all.
            _show_guidance(code, detail=st.session_state.home_error)
        else:
            st.error(st.session_state.home_error)

    _render_home_options()


@st.cache_data(show_spinner=False)
def _cached_process(
    raw: bytes,
    threshold: int,
    auto_invert: bool,
    crop_whitespace: bool,
    padding_percent: float,
    despeckle_size: int,
    thicken_pixels: int,
) -> bytes:
    return normalise_line_art(
        raw,
        ProcessingOptions(
            threshold=threshold,
            auto_invert=auto_invert,
            crop_whitespace=crop_whitespace,
            padding_percent=padding_percent,
            despeckle_size=despeckle_size,
            thicken_pixels=thicken_pixels,
        ),
    )


@st.cache_data(show_spinner=False)
def _cached_preview(pdf_bytes: bytes, dpi: int = 115) -> bytes:
    return render_pdf_preview(pdf_bytes, dpi=dpi)


@st.cache_data(show_spinner=False, max_entries=32)
def _cached_badge_preview(
    image_bytes: bytes, config_payload: str, calibration_payload: str
) -> bytes:
    # The configs arrive as sorted JSON because Streamlit's cache needs a
    # hashable key and the dataclasses are not hashable.
    config = CircleSheetConfig(**json.loads(config_payload))
    calibration = CalibrationProfile.from_dict(json.loads(calibration_payload))
    return render_badge_preview(image_bytes, config, calibration)


@st.cache_data(show_spinner=False, max_entries=32)
def _cached_badge_sheet_pdf(
    image_bytes: bytes, config_payload: str, calibration_payload: str
) -> bytes:
    """The actual A4 sheet of badges the strip's preview only shows a hint of.

    Built through the same create_circle_sheet_pdf every other circle-sheet
    export uses, so a printed sheet cannot drift from what Doodle Studio's own
    "A4 circle sheet" layout would produce from the identical config.
    """

    config = CircleSheetConfig(**json.loads(config_payload))
    calibration = CalibrationProfile.from_dict(json.loads(calibration_payload))
    pdf_bytes, _count = create_circle_sheet_pdf(image_bytes, config, calibration)
    return pdf_bytes


@st.cache_data(show_spinner=False)
def _calibration_pdf() -> bytes:
    return create_calibration_pdf()


@st.cache_data(show_spinner=False)
def _cached_characters(signature: tuple) -> list[Character]:
    return list_characters()


def _characters() -> list[Character]:
    """The saved cast, re-parsed from disk only when something about it has
    actually changed (FB-19/ARCH-02): every other disk-heavy read in this
    file is cached, but this one used to re-read and re-parse every
    character's JSON on every interaction anywhere on the screen it renders
    into, including one that has nothing to do with the cast."""

    return _cached_characters(characters_signature())


@st.cache_data(show_spinner=False, max_entries=128)
def _cached_character_portrait(
    character_id: str, portrait_mtime_ns: int
) -> bytes | None:
    return load_character_portrait(character_id)


def _character_portrait(character_id: str) -> bytes | None:
    """A character's portrait, decoded once and reused until that specific
    portrait file is rewritten — a redraw changes its own mtime and busts
    only its own cache entry, leaving every other character's untouched."""

    return _cached_character_portrait(
        character_id, character_portrait_mtime(character_id)
    )


def _set_current_artwork(raw: bytes, *, title: str, metadata: dict) -> None:
    st.session_state.current_raw = raw
    st.session_state.current_title = title
    st.session_state.current_metadata = metadata
    st.session_state.pdf_bytes = None
    st.session_state.pdf_summary = ""


def _slug(text: str, fallback: str = "doodle") -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return value[:64] or fallback


def _orientation_dimensions(orientation: str) -> tuple[float, float]:
    return (210.0, 297.0) if orientation == "Portrait" else (297.0, 210.0)


def _build_signature(
    image_bytes: bytes, kind: str, config: object, calibration: CalibrationProfile
) -> str:
    payload = {
        "kind": kind,
        "config": asdict(config),
        "calibration": calibration.to_dict(),
    }
    digest = hashlib.sha256()
    digest.update(image_bytes)
    digest.update(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    return digest.hexdigest()


def _start_version_chain(artwork) -> None:
    st.session_state.doodle_versions = history.start(artwork)
    st.session_state.current_version = 0


def _render_top_bar(*, where: str) -> None:
    """The logo and the two routes that must never be more than one click away.

    Starting a fresh doodle used to mean scrolling past the change box to a
    button at the very bottom, and reaching the saved doodles meant finding
    Doodle Studio first.
    """

    # The one place besides the homepage where injected styling is needed, and
    # for the same reason recorded there: the defect lives inside Streamlit's
    # own chrome and no native API reaches it. Nothing here changes what the
    # button does, only whether the parent sees a button or the wordmark.
    st.markdown(
        """
        <style>
          [class*="st-key-doodle-brand-"] {position:relative;}
          [class*="st-key-doodle-brand-"] [data-testid="stButton"] {
            position:absolute; inset:0; margin:0;
          }
          [class*="st-key-doodle-brand-"] [data-testid="stButton"] button {
            width:100%; height:100%; opacity:0; cursor:pointer;
            padding:0; min-height:0; border:none; background:transparent;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )
    brand, saved, fresh = st.columns([3, 1.5, 1.3])
    with brand:
        # The wordmark goes home, because every app with a logo in the corner
        # has taught people that it does. Streamlit has no way to make a
        # markdown block clickable, and an anchor cannot be clicked in a test,
        # so a real button is laid over the logo instead: it carries the label
        # a screen reader announces, and the CSS below makes it invisible.
        with st.container(key=f"doodle-brand-{where}"):
            st.markdown(_doodle_logo("compact"), unsafe_allow_html=True)
            if st.button(
                "Doodle, back to the homepage",
                key=f"top_brand_{where}",
                type="tertiary",
            ):
                _start_new_doodle()
    with saved:
        count = _saved_doodle_count()
        if st.button(
            f"Saved ({count})" if count else "Saved",
            width="stretch",
            icon=":material/collections_bookmark:",
            key=f"top_saved_{where}",
            disabled=not count,
            help="Every doodle you have saved on this computer."
            if count
            else "Nothing saved yet.",
        ):
            st.session_state.library_return = where
            st.session_state.screen = "library"
            st.rerun()
    with fresh:
        if st.button(
            "New doodle",
            width="stretch",
            icon=":material/add:",
            key=f"top_new_{where}",
        ):
            _start_new_doodle()


def _colour_key(image_bytes: bytes) -> str:
    return hashlib.sha256(image_bytes).hexdigest()


def _render_doodle_with_colours(image_bytes: bytes, *, key_prefix: str) -> None:
    """The picture, with the option of seeing it coloured in as a guide.

    A toddler deciding what colour water or grass should be has nothing to copy
    from a page of outlines. The coloured version is only ever shown on screen:
    the PDF that gets printed is always the line art, because the point of the
    thing is that a child colours it.
    """

    cache = st.session_state.setdefault("colour_previews", {})
    key = _colour_key(image_bytes)
    coloured = cache.get(key)
    showing = bool(st.session_state.get("showing_colours")) and coloured is not None

    st.image(coloured if showing else image_bytes, width="stretch")

    provider_id = _active_provider_id()
    spec = get_provider(provider_id)
    api_key, _source = _provider_key(provider_id)

    if showing:
        st.caption(
            "Suggested colours, for copying from. The page you print stays "
            "black and white."
        )
        if st.button(
            "Show the outlines",
            key=f"{key_prefix}_hide_colours",
            width="stretch",
            icon=":material/gesture:",
        ):
            st.session_state.showing_colours = False
            st.rerun()
        return

    if coloured is not None:
        if st.button(
            "Show suggested colours",
            key=f"{key_prefix}_show_colours",
            width="stretch",
            icon=":material/palette:",
        ):
            st.session_state.showing_colours = True
            st.rerun()
        return

    if not spec.supports_edit:
        st.caption(
            f"{spec.label} cannot colour a picture in. Connect OpenAI or Google Gemini to try it."
        )
        return

    if not st.button(
        "Colour it in for me",
        key=f"{key_prefix}_make_colours",
        width="stretch",
        icon=":material/palette:",
        help="Draws a coloured copy to compare against. Costs one generation, and is never printed.",
        disabled=not api_key,
    ):
        return
    colour_busy_key = f"busy_colour_{key_prefix}"
    if _drawing_already_in_flight(colour_busy_key):
        # A queued replay of a click already being handled.
        return

    settings = load_settings()
    model = _model_for(provider_id, spec, settings)

    try:
        with _mark_in_flight(colour_busy_key):
            with st.spinner("Choosing colours…"):
                artwork = refine_with_provider(
                    provider_id=provider_id,
                    api_key=api_key,
                    image_bytes=image_bytes,
                    prompt=build_colour_suggestion_prompt(
                        [
                            (name, appearance)
                            for _, name, _, _, appearance in _recorded_cast()
                        ]
                    ),
                    model=model,
                    size=spec.portrait_size,
                )
    except GeneratorError as exc:
        _show_guidance(exc.code, detail=str(exc))
        return

    cache[key] = artwork.image_bytes
    st.session_state.colour_previews = cache
    st.session_state.showing_colours = True
    st.rerun()


def _render_alternatives_picker() -> None:
    """The other readings of the same idea, when more than one was drawn."""

    candidates = st.session_state.get("candidates") or []
    if len(candidates) < 2:
        return

    st.caption("Doodle drew these from the same idea. Tap one to work on it instead.")
    columns = st.columns(len(candidates))
    for index, candidate in enumerate(candidates):
        with columns[index]:
            st.image(candidate.image_bytes, width="stretch")
            chosen = candidate.image_bytes == st.session_state.get("current_raw")
            if st.button(
                "Showing" if chosen else "Use this one",
                key=f"quick_candidate_{index}",
                width="stretch",
                disabled=chosen,
            ):
                _adopt_artwork(
                    candidate,
                    st.session_state.current_metadata.get("concept", "Doodle"),
                    characters=candidate.metadata.get("characters", []),
                )
                _prepare_quick_outputs()
                st.rerun()

    with st.expander("How these differ"):
        for index, candidate in enumerate(candidates, start=1):
            st.markdown(f"**Picture {index}**")
            st.caption(
                candidate.metadata.get("brief") or "Drawn from the idea as written."
            )


def _remember_chosen(character_id: str) -> None:
    """Widget keys vanish when their widget is not rendered, so the answer
    lives in a plain key and each box is told its value on the way in.

    toggle_chosen (colouring_factory.characters) is the pure add-or-remove
    logic; this is only the session-state read and write around it.
    """

    ticked = bool(st.session_state.get(f"character_pick_{character_id}"))
    st.session_state.chosen_characters = toggle_chosen(
        st.session_state.get("chosen_characters", []), character_id, ticked=ticked
    )


def _render_home_options() -> None:
    """The questions the homepage asks before it draws anything.

    Pressing Enter used to draw one picture on fixed settings, with the only
    controls for them buried in Doodle Studio, behind the drawing that had
    already been paid for. Answering them in a panel below the bar turned the
    page into a stack of boxes, so the answers are a line of small grey text
    instead, and each one opens its choices in a floating panel rather than
    pushing the page around. Who is in the picture joins the same line, once
    there is a saved cast to put in it.
    """

    settings = load_settings()
    options = quick_drawing_options(settings)

    # Read the widgets' own state for the labels. The saved settings are one
    # rerun behind the control the user has just moved, so a label built from
    # them would describe the previous choice.
    shown_alternatives = (
        st.session_state.get("home_alternatives") or options["alternatives"]
    )
    shown_age = st.session_state.get("home_age_profile") or options["age_profile"]
    shown_style = st.session_state.get("home_style") or options["style"]
    plural = "" if int(shown_alternatives) == 1 else "s"

    pairing = bool(st.session_state.get("home_pair_grown_up", options["pair_grown_up"]))
    pairing = pairing and shown_age != GROWN_UP_LEVEL
    age_label = f"{shown_age} + grown-up" if pairing else str(shown_age)

    # Read-through against the current cast, the same discipline
    # quick_drawing_options applies to the saved settings: an id left over
    # from a character who has since been deleted must not be counted.
    chosen_ids = set(st.session_state.get("chosen_characters", []))
    cast = _characters()
    active_spec = get_provider(_active_provider_id())

    with st.container(
        key="doodle-home-settings",
        horizontal=True,
        horizontal_alignment="center",
        vertical_alignment="center",
        gap="small",
    ):
        with st.popover(f"{shown_alternatives} picture{plural}", type="tertiary"):
            alternatives = st.segmented_control(
                "How many to draw",
                list(QUICK_ALTERNATIVE_CHOICES),
                default=options["alternatives"],
                key="home_alternatives",
                help="Each one is drawn separately, from its own reading of your idea, and costs one generation.",
            )
        with st.popover(age_label, type="tertiary"):
            age_profile = st.segmented_control(
                "Who it is for",
                list(QUICK_AGE_CHOICES),
                default=options["age_profile"],
                key="home_age_profile",
                help="Grown-up draws the intricate kind of page an adult colours to unwind.",
            )
            # Offered only where it means something. Asking a grown-up sheet to
            # be paired with a grown-up sheet would draw the same thing twice.
            if (age_profile or options["age_profile"]) != GROWN_UP_LEVEL:
                pair_grown_up = st.checkbox(
                    "Also draw one for me, at grown-up detail",
                    value=options["pair_grown_up"],
                    key="home_pair_grown_up",
                    help=(
                        "Draws your idea twice from one description of the scene: "
                        "the sheet above for the children and an intricate one for "
                        "you, so you can all colour the same picture. Two pictures, "
                        "whatever How many to draw says."
                    ),
                )
            else:
                pair_grown_up = False
        with st.popover(str(shown_style).lower(), type="tertiary"):
            style = st.selectbox(
                "Drawing style",
                list(QUICK_STYLE_CHOICES),
                index=list(QUICK_STYLE_CHOICES).index(options["style"]),
                key="home_style",
            )
        # Rendered from the first run, unlike Saved doodles (n) in the
        # corner: hiding this until a cast existed left no control anywhere
        # that reached the characters screen, so a parent could never add
        # their first character. Hidden only when the active service cannot
        # look at a reference picture at all, in which case nothing here
        # could work regardless of what is saved.
        if active_spec.max_reference_images >= 1:
            cast_ids = {character.id for character in cast}
            count = len(chosen_ids & cast_ids)
            limit = active_spec.max_reference_images
            # A face rather than a word, because this item answers "who" while
            # its three neighbours answer "how", and the icon says so at a
            # glance without spending any of the line's width. The count sits
            # beside it when there is one; alone, the face reads as nobody yet.
            label = "" if not count else str(count)
            # The trigger label stays a count, never a list of names: the
            # settings line it sits on cannot shrink or ellipsise. The portrait
            # is what tells two same-named characters apart (a girl and her
            # teddy both called Ida), so it lives inside the panel instead.
            with st.popover(label, type="tertiary", icon=":material/face:"):
                if cast:
                    st.caption(
                        "Doodle draws these characters into the picture. "
                        f"{active_spec.label} looks at up to {limit} at once."
                    )
                    for character in cast:
                        ticked = character.id in chosen_ids
                        portrait_col, tick_col = st.columns(
                            [1, 4], vertical_alignment="center"
                        )
                        with portrait_col:
                            portrait = _character_portrait(character.id)
                            if portrait is not None:
                                st.image(portrait, width=36)
                            else:
                                st.markdown(":material/broken_image:")
                        with tick_col:
                            st.checkbox(
                                character.name,
                                key=f"character_pick_{character.id}",
                                value=ticked,
                                on_change=_remember_chosen,
                                args=(character.id,),
                                # Ticking past what the connected service will
                                # look at builds a request that cannot
                                # succeed, so the box is disabled once the cap
                                # is reached rather than left to fail later.
                                # An already-ticked box stays enabled, so
                                # unticking back under the cap is possible.
                                disabled=not ticked and count >= limit,
                            )
                else:
                    st.caption(
                        "Save a person, toy or character once, then put them "
                        "in any picture Doodle draws."
                    )
                if st.button("Add a character", width="stretch"):
                    st.session_state.screen = "characters"
                    st.rerun()
        else:
            st.caption(
                f"{active_spec.label} cannot draw from a picture of someone. "
                "Connect OpenAI or Google Gemini to add characters."
            )

    # A segmented control returns None when its selection is cleared, which
    # would otherwise write a null into the settings file.
    chosen = {
        "quick_alternatives": int(alternatives or options["alternatives"]),
        "quick_age_profile": str(age_profile or options["age_profile"]),
        "quick_style": str(style or options["style"]),
        "quick_pair_grown_up": bool(pair_grown_up),
    }
    if any(settings.get(key) != value for key, value in chosen.items()):
        save_settings({**settings, **chosen})


def _adopt_artwork(artwork, idea: str, *, characters: list[str]) -> None:
    """Make one generated picture the current doodle, starting its history.

    `characters` is who the picture was actually drawn with, stamped here
    rather than trusted to already be on artwork.metadata: this is the one
    function every adoption path shares, so it is the one place a cast
    cannot be silently dropped by a caller that forgets to carry it
    forward. A badge redraw used to lose the cast this way on its very
    first press, because the fresh artwork it adopted carried the
    provider's own metadata, not the characters key the previous picture
    had recorded.
    """

    _set_current_artwork(
        artwork.image_bytes,
        title=idea,
        metadata={
            "source": artwork.provider,
            "concept": idea,
            "prompt": artwork.prompt,
            "model": artwork.model,
            "generation": {**artwork.metadata, "characters": characters},
        },
    )
    _start_version_chain(artwork)


def _send_to_printer(pdf_bytes: bytes) -> None:
    """Open the browser's print dialogue on this PDF.

    Downloading was never the point of these files. Every layout in Doodle is
    measured in millimetres for a printer, so the button that finishes the job
    has to reach the print dialogue rather than the Downloads folder.
    """

    nonce = int(st.session_state.get("print_nonce", 0)) + 1
    st.session_state.print_nonce = nonce
    st.html(
        print_trigger_html(pdf_bytes, nonce=f"doodle-print-{nonce}"),
        unsafe_allow_javascript=True,
    )


def _render_print_help(
    pdf_bytes: bytes, *, file_name: str, key: str, scale_note: bool = True
) -> None:
    """The scale warning, and a way out when the browser blocks printing."""

    if scale_note:
        st.caption(
            "In the print dialogue set Scale to 100% (Actual size) and turn off "
            "Fit to page, or the sizes will not come out as measured."
        )
    with st.expander("Nothing happened when I pressed print"):
        st.write(
            "Some browsers refuse to open a print dialogue on a page's behalf. "
            "Save the PDF and print it from Preview or Adobe Reader instead, "
            "using the same Actual size setting."
        )
        st.download_button(
            "Download the PDF",
            data=pdf_bytes,
            file_name=file_name,
            mime="application/pdf",
            width="stretch",
            key=f"download_pdf_{key}",
            icon=":material/download:",
        )


def _saved_doodle_count() -> int:
    return len(list_library_items())


def _render_library_grid() -> None:
    """The grid of saved doodles, shared by the Saved screen and the Studio tab.

    Loading a doodle always ends up in Doodle Studio, because laying a picture
    out and printing it is the only reason to reopen one.
    """

    items = list_library_items()
    if not items:
        st.info(
            "You have no saved doodles yet. Draw a picture, then press Save to your doodles."
        )
        return

    columns = st.columns(3)
    for index, item in enumerate(items):
        with columns[index % 3]:
            with st.container(border=True):
                st.image(item["processed_path"], width="stretch")
                st.markdown(f"**{item.get('title', 'Untitled doodle')}**")
                created = item.get("created_at", "")
                try:
                    readable = datetime.fromisoformat(created).strftime(
                        "%d %b %Y, %H:%M"
                    )
                except ValueError:
                    readable = created
                st.caption(readable)
                source = item.get("metadata", {}).get("source", "Unknown source")
                st.caption(f"Source: {source}")

                if st.session_state.get("pending_delete") == item["id"]:
                    # Deleting a saved doodle removes the only copy, so the
                    # second click is the one that does it.
                    st.warning("Delete this doodle? This cannot be undone.")
                    confirm_col, cancel_col = st.columns(2)
                    with confirm_col:
                        if st.button(
                            "Delete for good",
                            key=f"confirm_delete_{item['id']}",
                            width="stretch",
                            icon=":material/delete_forever:",
                        ):
                            delete_library_item(item["id"])
                            st.session_state.pending_delete = ""
                            st.rerun()
                    with cancel_col:
                        if st.button(
                            "Keep it",
                            key=f"cancel_delete_{item['id']}",
                            width="stretch",
                        ):
                            st.session_state.pending_delete = ""
                            st.rerun()
                    continue

                use_col, delete_col = st.columns(2)
                with use_col:
                    if st.button(
                        "Open",
                        key=f"load_{item['id']}",
                        width="stretch",
                        icon=":material/open_in_new:",
                    ):
                        _set_current_artwork(
                            load_library_image(item["id"], prefer_raw=False),
                            title=item.get("title", "Saved doodle"),
                            metadata={
                                "source": "Saved doodles",
                                "library_id": item["id"],
                            },
                        )
                        st.session_state.library_notice = (
                            f"{item.get('title', 'Your doodle')} is open. "
                            "Lay it out below, then build the PDF."
                        )
                        st.session_state.screen = "studio"
                        st.rerun()
                with delete_col:
                    if st.button(
                        "Delete",
                        key=f"delete_{item['id']}",
                        width="stretch",
                        icon=":material/delete:",
                    ):
                        st.session_state.pending_delete = item["id"]
                        st.rerun()


def _render_library_screen() -> None:
    st.markdown(_doodle_logo("compact"), unsafe_allow_html=True)
    st.header("Saved doodles")
    st.caption(f"Kept on this computer, in {data_root()}.")

    _render_library_grid()

    st.divider()
    back_col, new_col = st.columns(2)
    with back_col:
        target = str(st.session_state.get("library_return", "home"))
        label = "Back to your doodle" if target == "result" else "Back"
        if st.button(label, width="stretch", icon=":material/arrow_back:"):
            st.session_state.screen = target if target != "library" else "home"
            st.rerun()
    with new_col:
        if st.button("New doodle", width="stretch", icon=":material/add:"):
            _start_new_doodle()


# The segmented control speaks the way a parent would ("A toy"); the storage
# layer speaks its own fixed vocabulary. Built from CHARACTER_KINDS, not
# hardcoded, so the two cannot drift apart if a kind is ever added there.
CHARACTER_KIND_LABELS = dict(
    zip(("A person", "A toy", "Something else"), CHARACTER_KINDS)
)


def _draw_character_portrait(
    photo: bytes, name: str, kind: str, marks: str, appearance: str = ""
) -> GeneratedArtwork:
    """Draw one caricature from a reference photograph.

    Uses the provider's square size, not its portrait size: a caricature is
    nothing but a face, and a face is the most badge-shaped thing Doodle draws.
    """

    provider_id = _active_provider_id()
    spec = get_provider(provider_id)
    api_key, _source = _provider_key(provider_id)
    settings = load_settings()
    return refine_with_provider(
        provider_id=provider_id,
        api_key=api_key,
        prompt=build_caricature_prompt(name, kind, marks, appearance),
        reference_images=(photo,),
        model=_model_for(provider_id, spec, settings),
        size=spec.square_size,
        quality=str(settings.get("openai_quality", DEFAULT_QUALITY)),
    )


def _open_character_portrait_as_doodle(character) -> None:
    """Adopt an already-drawn portrait as the current doodle.

    Reads the picture already on disk rather than drawing anything new, so
    this costs nothing: adding someone to the cast and getting a printable
    cartoon of their photograph are two different things a parent can want,
    and this is the deliberate route to the second one, for a character
    added just now or weeks ago alike.
    """

    portrait_bytes = load_character_image(character.id, portrait=True)
    concept = f"{character.name}, drawn by Doodle"
    # A portrait has no scene idea behind it, but "Draw this idea again" on
    # the result screen always reads generation_idea: leaving it empty made
    # that button raise missing_prompt the first time this route was used.
    st.session_state.generation_idea = concept
    _adopt_artwork(
        GeneratedArtwork(
            image_bytes=portrait_bytes, prompt="", provider="Doodle", model=""
        ),
        concept,
        characters=[character.id],
    )
    _prepare_quick_outputs()
    st.session_state.screen = "result"
    st.rerun()


def _render_characters_screen() -> None:
    """Add a face to the cast, and see who is already in it.

    Adding someone to the cast and getting a printable cartoon of their
    photograph are two different things a parent can want, so this screen
    stays on itself once a character is drawn or redrawn: a confirmation
    names who changed, and every tile carries its own route to open that
    portrait as a doodle when a print of it is what was actually wanted.
    """

    _render_top_bar(where="characters")

    # The homepage's "Add a character" button is the only route here, so Back
    # always has exactly one place to return to.
    if st.button("Back", width="stretch", icon=":material/arrow_back:"):
        st.session_state.screen = "home"
        st.rerun()

    st.header("Your characters")

    if st.session_state.get("character_notice"):
        st.success(st.session_state.character_notice, icon=":material/check:")
        st.session_state.character_notice = ""
    if st.session_state.get("character_duplicate_notice"):
        st.info(st.session_state.character_duplicate_notice, icon=":material/info:")
        st.session_state.character_duplicate_notice = ""

    provider_id = _active_provider_id()
    spec = get_provider(provider_id)
    api_key, _source = _provider_key(provider_id)
    kind_label_for_kind = {kind: label for label, kind in CHARACTER_KIND_LABELS.items()}
    # A redraw always sends the stored photograph as a reference picture, the
    # same call shape as drawing a character in for the first time, so it
    # needs the same capability rather than only a key: on Recraft it used to
    # disable on nothing, fail after the click, and explain itself only then.
    can_redraw = bool(api_key) and spec.max_reference_images >= 1
    # Describing a photograph is a text call, not an image one, so it needs
    # a text model rather than reference-image support — Recraft fails this
    # even though nothing about it stops it drawing a portrait.
    can_describe = bool(api_key) and bool(spec.text_model)

    characters = _characters()
    if not characters:
        st.info("No characters yet. Add your first one below.")
    else:
        columns = st.columns(3)
        for index, character in enumerate(characters):
            with columns[index % 3]:
                with st.container(border=True):
                    # A zero-byte or truncated portrait.png (a cloud-sync
                    # placeholder, a disk fault) used to raise deep inside
                    # st.image and take the whole screen down with it — every
                    # character after the bad one, and the add form, gone
                    # with no control left on the page to reach it. Degrading
                    # to a placeholder keeps the name and the delete button.
                    portrait = _character_portrait(character.id)
                    if portrait is not None:
                        st.image(portrait, width="stretch")
                    else:
                        st.info(
                            "This picture could not be shown.",
                            icon=":material/broken_image:",
                        )
                    st.markdown(f"**{character.name}**")

                    if portrait is not None and st.button(
                        "Open as a doodle",
                        key=f"open_as_doodle_{character.id}",
                        width="stretch",
                        icon=":material/open_in_new:",
                        help=(
                            "Prints, saves and colours their portrait like "
                            "any other doodle. Draws nothing new."
                        ),
                    ):
                        _open_character_portrait_as_doodle(character)

                    if st.session_state.get("pending_character_delete") == character.id:
                        # Deleting a character removes the only copy of their
                        # picture, so the second click is the one that does it.
                        st.warning("Delete this character? This cannot be undone.")
                        confirm_col, cancel_col = st.columns(2)
                        with confirm_col:
                            if st.button(
                                "Delete for good",
                                key=f"confirm_delete_character_{character.id}",
                                width="stretch",
                                icon=":material/delete_forever:",
                            ):
                                delete_character(character.id)
                                st.session_state.pending_character_delete = ""
                                st.session_state.chosen_characters = [
                                    chosen
                                    for chosen in st.session_state.chosen_characters
                                    if chosen != character.id
                                ]
                                st.rerun()
                        with cancel_col:
                            if st.button(
                                "Keep them",
                                key=f"cancel_delete_character_{character.id}",
                                width="stretch",
                            ):
                                st.session_state.pending_character_delete = ""
                                st.rerun()
                    elif st.button(
                        "Delete",
                        key=f"delete_character_{character.id}",
                        width="stretch",
                        icon=":material/delete:",
                    ):
                        st.session_state.pending_character_delete = character.id
                        st.rerun()

                    with st.expander("Edit"):
                        # The repair for a typo or a bad likeness: change the
                        # words with no redraw, or redraw from the photograph
                        # already on disk with no fresh upload. Delete was
                        # the only control before this, and it destroys the
                        # photograph, so fixing a spelling mistake used to
                        # cost a re-upload and a paid drawing.
                        edit_name = st.text_input(
                            "Name",
                            value=character.name,
                            key=f"edit_name_{character.id}",
                        )
                        edit_kind_label = st.segmented_control(
                            "What are they",
                            list(CHARACTER_KIND_LABELS),
                            default=kind_label_for_kind.get(character.kind, "A person"),
                            key=f"edit_kind_{character.id}",
                        )
                        edit_marks = st.text_area(
                            "What makes them recognisable",
                            value=character.marks,
                            key=f"edit_marks_{character.id}",
                            height=90,
                        )
                        edit_appearance = st.text_area(
                            "How they really look",
                            value=character.appearance,
                            key=f"edit_appearance_{character.id}",
                            height=90,
                            placeholder=(
                                "Brown eyes, wavy dark-brown hair to her "
                                "shoulders, light-brown skin."
                            ),
                            help=(
                                "Used to keep their hair, eyes and skin "
                                "right when Doodle draws and colours them in."
                            ),
                        )
                        if st.button(
                            "Save changes",
                            key=f"save_character_{character.id}",
                            width="stretch",
                            icon=":material/save:",
                        ):
                            if not edit_name.strip():
                                st.error("Give them a name.")
                            else:
                                update_character(
                                    character.id,
                                    name=edit_name,
                                    kind=CHARACTER_KIND_LABELS.get(
                                        edit_kind_label or "A person", "person"
                                    ),
                                    marks=edit_marks,
                                    appearance=edit_appearance,
                                )
                                st.rerun()

                        if not character.appearance.strip():
                            # The repair an existing character with no
                            # description needs, without a fresh upload: the
                            # redraw button below already loads this same
                            # stored photograph.
                            describe_busy_key = f"busy_describe_{character.id}"
                            if st.button(
                                "Fill in from their photo",
                                key=f"describe_character_{character.id}",
                                width="stretch",
                                icon=":material/auto_fix_high:",
                                disabled=not can_describe,
                                help=(
                                    "Drafts their hair, eyes and skin from "
                                    "the photo already on file. Costs one "
                                    "short text description."
                                ),
                            ) and not _drawing_already_in_flight(describe_busy_key):
                                try:
                                    stored_photo = load_character_image(
                                        character.id, portrait=False
                                    )
                                    with _mark_in_flight(describe_busy_key):
                                        with st.spinner(
                                            f"Describing {character.name}…"
                                        ):
                                            description = describe_appearance(
                                                stored_photo,
                                                provider_id=provider_id,
                                                api_key=api_key,
                                            )
                                except GeneratorError as exc:
                                    _show_guidance(exc.code, detail=str(exc))
                                else:
                                    update_character(
                                        character.id,
                                        name=character.name,
                                        kind=character.kind,
                                        marks=character.marks,
                                        appearance=description,
                                    )
                                    st.rerun()

                        if not can_redraw and api_key:
                            # The key exists, so this is the capability gap,
                            # not the missing-key one: name it in advance
                            # rather than let the button fail after a click.
                            st.caption(
                                f"{spec.label} cannot draw from a picture of "
                                "someone. Connect OpenAI or Google Gemini to "
                                "redraw a portrait."
                            )
                        redraw_busy_key = f"busy_redraw_{character.id}"
                        if st.button(
                            "Redraw their portrait",
                            key=f"redraw_character_{character.id}",
                            width="stretch",
                            icon=":material/auto_awesome:",
                            disabled=not can_redraw,
                            help=(
                                "Draws a fresh portrait from the photo "
                                "already on file. Costs one generation."
                            ),
                        ) and not _drawing_already_in_flight(redraw_busy_key):
                            try:
                                stored_photo = load_character_image(
                                    character.id, portrait=False
                                )
                                with _mark_in_flight(redraw_busy_key):
                                    with st.spinner(f"Redrawing {character.name}…"):
                                        new_portrait = _draw_character_portrait(
                                            stored_photo,
                                            character.name,
                                            character.kind,
                                            character.marks,
                                            character.appearance,
                                        )
                            except GeneratorError as exc:
                                _show_guidance(exc.code, detail=str(exc))
                            else:
                                update_character_portrait(
                                    character.id, new_portrait.image_bytes
                                )
                                # A repair to the cast, like "Save changes"
                                # beside it, not a doodle: stay here, naming
                                # who was redrawn, rather than jump to the
                                # result screen as if a fresh idea had been
                                # drawn.
                                st.session_state.character_notice = (
                                    f"{character.name}'s portrait has been redrawn."
                                )
                                st.rerun()

    st.divider()
    st.subheader("Add a character")
    # The only screen that asks for a photograph of a child, so the fact and
    # the consequence belong right here, not on a Studio tab this journey
    # never visits. The photograph is sent every time a picture is drawn
    # with this character, not just once: see _draw_character_portrait and
    # every load_character_image(..., portrait=False) call site.
    st.caption(
        "Their photograph is sent to the drawing service you have "
        "connected, each time a picture is drawn with them — now, for "
        "their portrait, and again for every scene or badge afterwards. "
        "As soon as you choose it, the same service is also asked to "
        "describe their hair, eyes and skin, so drawings and colouring "
        "match them — check the description below and correct anything it "
        "gets wrong. Removing a character deletes the copy Doodle holds."
    )

    uploaded = st.file_uploader(
        "Add a picture",
        type=["png", "jpg", "jpeg", "webp", "heic"],
        accept_multiple_files=False,
        help="A clear photo of their face works best.",
    )

    if uploaded is not None and api_key and spec.text_model:
        # Fired once per distinct photo, not on every rerun: every widget on
        # this form triggers one, and Streamlit gives no other signal that
        # the file itself, rather than some other field, is what changed.
        photo_hash = hashlib.sha256(uploaded.getvalue()).hexdigest()
        if st.session_state.get("character_appearance_draft_hash") != photo_hash:
            try:
                draft_photo = prepare_photo(uploaded.getvalue())
                draft = describe_appearance(
                    draft_photo, provider_id=provider_id, api_key=api_key
                )
            except (ValueError, GeneratorError):
                # Best-effort: a photo that cannot be described yet is not a
                # reason to block the form. The text area below is still
                # there, blank, for the parent to fill in by hand.
                draft = ""
            st.session_state.character_appearance = draft
            st.session_state.character_appearance_draft_hash = photo_hash

    name = st.text_input("Name", key="character_name")
    kind_label = st.segmented_control(
        "What are they",
        list(CHARACTER_KIND_LABELS),
        default="A person",
        key="character_kind",
    )
    marks = st.text_area(
        "What makes them recognisable",
        key="character_marks",
        height=90,
        placeholder="Curly hair, round glasses, a gap in her front teeth.",
    )
    appearance = st.text_area(
        "How they really look",
        key="character_appearance",
        height=90,
        placeholder="Brown eyes, wavy dark-brown hair to her shoulders, light-brown skin.",
        help=(
            "Drafted from the photo, so the drawing and the colouring both "
            "match them. Correct anything it gets wrong."
        ),
    )

    if spec.max_reference_images < 1:
        # The same rule as "Colour it in for me": read the capability and do
        # not offer a button that can only fail, rather than let the parent
        # press it and be told to change provider on a screen they are not on.
        st.caption(
            f"{spec.label} cannot draw from a picture of someone. Connect "
            "OpenAI or Google Gemini to add a character."
        )
        return

    if not api_key:
        # Mirrors the capability guard above: a disabled button with no
        # explanation and no route to the Connect screen was a dead end for
        # any parent who explored the cast before typing an idea, which the
        # settings-line popover's own copy invites them to do.
        st.caption(f"Connect {spec.label}, or another provider, to add a character.")
        if st.button("Connect a provider", width="stretch", icon=":material/link:"):
            st.session_state.connect_return = "characters"
            st.session_state.screen = "connect"
            st.rerun()
        return

    if st.button(
        "Draw them",
        type="primary",
        width="stretch",
        icon=":material/auto_awesome:",
        help=(
            "Draws their portrait and saves them to your cast. Costs one "
            "generation, plus one short text description from their photo."
        ),
    ):
        if _drawing_already_in_flight("busy_add_character"):
            # A queued replay of a click already being handled. Drawing
            # again from here bought a real parent six identical characters
            # from what he experienced as one press each.
            return
        if not uploaded:
            st.error("Add a picture first.")
            return
        typed_name = name.strip()
        if not typed_name:
            st.error("Give them a name.")
            return

        try:
            photo = prepare_photo(uploaded.getvalue())
        except ValueError as exc:
            st.error(str(exc))
            return

        kind = CHARACTER_KIND_LABELS.get(kind_label or "A person", "person")
        # Read before saving: a name shared with someone already in the cast
        # is a duplicate worth mentioning, not a reason to compare the new
        # arrival with themselves.
        is_duplicate_name = typed_name.casefold() in {
            existing.name.casefold() for existing in characters
        }
        try:
            with _mark_in_flight("busy_add_character"):
                with st.spinner(f"Drawing {typed_name}…"):
                    artwork = _draw_character_portrait(
                        photo, typed_name, kind, marks, appearance
                    )
        except GeneratorError as exc:
            # Nothing is saved on a decline: a character with no portrait must
            # never reach the store.
            _show_guidance(exc.code, detail=str(exc))
            return

        save_character(
            photo=photo,
            portrait=artwork.image_bytes,
            name=typed_name,
            kind=kind,
            marks=marks,
            appearance=appearance,
        )
        # Adding someone to the cast is its own action, not a doodle in
        # disguise: stay here, naming who was added, rather than jump to a
        # screen headed "Your Doodle is ready" for a picture with no scene.
        st.session_state.character_notice = f"{typed_name} is in your characters now."
        if is_duplicate_name:
            st.session_state.character_duplicate_notice = (
                f'Another character is already named "{typed_name}". Doodle '
                "keeps both — their photograph is what tells them apart in "
                "the picker."
            )
        st.rerun()


def _render_refine_controls(*, key_prefix: str) -> None:
    """The refine box and the version strip beneath a picture."""

    chain = st.session_state.get("doodle_versions", ())
    if not chain:
        return

    provider_id = _active_provider_id()
    spec = get_provider(provider_id)
    api_key, _source = _provider_key(provider_id)
    current = int(st.session_state.get("current_version", 0))

    if len(chain) > 1:
        st.caption(f"{len(chain)} versions drawn in this chain")
        strip = st.columns(min(len(chain), 6))
        for index, version in enumerate(chain):
            with strip[index % len(strip)]:
                st.image(version.artwork.image_bytes, width="stretch")
                label = version.instruction or "Original"
                if index == current:
                    st.caption(f"**{label}** — showing")
                else:
                    st.caption(label)
                    if st.button(
                        "Go back to this",
                        key=f"{key_prefix}_pick_{index}",
                        width="stretch",
                        icon=":material/history:",
                    ):
                        st.session_state.current_version = index
                        _set_current_artwork(
                            version.artwork.image_bytes,
                            title=st.session_state.current_title,
                            metadata=st.session_state.current_metadata,
                        )
                        # _set_current_artwork only sets current_raw: without
                        # rebuilding quick_processed/quick_pdf here too, the
                        # result screen kept showing the version just left.
                        _prepare_quick_outputs()
                        st.rerun()

    with st.form(f"{key_prefix}_refine", clear_on_submit=True):
        instruction = st.text_input(
            "Make a change",
            placeholder="Give the dinosaur a party hat",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button(
            "Change it", type="primary", width="stretch", icon=":material/edit:"
        )

    st.caption(
        "The whole picture is redrawn, so parts you did not ask about may shift "
        "a little. Each change costs one generation."
    )

    if not submitted:
        return
    if not instruction.strip():
        _show_guidance("missing_prompt")
        return
    if not api_key:
        _show_guidance("missing_key")
        return
    refine_busy_key = f"busy_refine_{key_prefix}"
    if _drawing_already_in_flight(refine_busy_key):
        # A queued replay of a click already being handled.
        return

    base = chain[current]
    settings = load_settings()
    model = _model_for(provider_id, spec, settings)

    try:
        prompt = build_refinement_prompt(instruction)
        with _mark_in_flight(refine_busy_key):
            with st.spinner("Making that change…"):
                artwork = refine_with_provider(
                    provider_id=provider_id,
                    api_key=api_key,
                    image_bytes=base.artwork.image_bytes,
                    prompt=prompt,
                    model=model,
                    size=spec.portrait_size,
                )
    except GeneratorError as exc:
        # The chain is untouched, so a failed change costs nothing but the call.
        _show_guidance(exc.code, detail=str(exc))
        return
    except ValueError as exc:
        _show_guidance("missing_prompt", detail=str(exc))
        return

    st.session_state.doodle_versions = history.append(
        chain, artwork, instruction, parent=current
    )
    st.session_state.current_version = len(st.session_state.doodle_versions) - 1
    _set_current_artwork(
        artwork.image_bytes,
        title=st.session_state.current_title,
        metadata={**st.session_state.current_metadata, "instruction": instruction},
    )
    # _set_current_artwork only sets current_raw: without rebuilding
    # quick_processed/quick_pdf here too, the result screen kept showing the
    # picture from before the change, so pressing "Change it" appeared to do
    # nothing at all.
    _prepare_quick_outputs()
    st.rerun()


def _apply_sheet_margin(value_mm: float) -> None:
    """Set the outer-margin widget's value.

    Assigning to a widget's session-state key from the script body raises, because
    the widget has already been instantiated by the time the click is handled. A
    callback runs before the rerun, while the key is still free.
    """

    st.session_state.circle_margin_mm = float(value_mm)


def _offer_margin_fix(suggested_mm: float) -> None:
    st.button(
        f"Set the margin to {suggested_mm:g} mm",
        width="stretch",
        icon=":material/straighten:",
        key=f"apply_margin_{suggested_mm:g}",
        on_click=_apply_sheet_margin,
        args=(suggested_mm,),
    )


def _show_guidance(code: str, *, detail: str = "", **context) -> None:
    """Explain a failure and name the control that owns the fix.

    Streamlit cannot reliably scroll to a widget, so the panel names the
    responsible setting rather than pretending to navigate to it.
    """

    entry = guidance_for(code, **context)
    st.error(f"**{entry.title}** — {detail or entry.cause}")
    with st.container(border=True):
        st.markdown(entry.fix)
        st.caption(f"Where: {entry.control}")


def _provider_connection_message(error: GeneratorError) -> dict[str, object]:
    return {
        "message": str(error),
        "code": getattr(error, "code", "unknown"),
        "provider": getattr(error, "provider", "")
        or get_provider(_active_provider_id()).label,
    }


def _continue_after_connection() -> None:
    destination = str(st.session_state.get("connect_return", "generate"))
    st.session_state.connection_error = None
    st.session_state.connect_replace = False
    if destination == "generate":
        st.session_state.quick_mode = "ai"
    st.session_state.screen = (
        destination
        if destination in {"generate", "studio", "result", "characters"}
        else "generate"
    )
    st.rerun()


def _render_connection_setup() -> None:
    st.markdown(
        """
        <style>
          [data-testid="stHeader"], [data-testid="stToolbar"],
          [data-testid="collapsedControl"], [data-testid="stSidebar"] {display:none!important;}
          .block-container, [data-testid="stMainBlockContainer"] {
            max-width: 720px!important;
            padding-top: clamp(2.25rem, 6vh, 4rem)!important;
            padding-bottom: 4rem!important;
          }
          .connection-title {text-align:center;font-size:1.65rem;font-weight:780;margin:.55rem 0 .35rem;}
          .connection-subtitle {text-align:center;color:#676b70;font-size:1rem;margin:0 auto 1.6rem;max-width:560px;}
          .idea-waiting {border:1px solid #e4e7eb;border-radius:1rem;background:#fafafa;padding:.9rem 1rem;margin:0 0 1.25rem;}
          .idea-waiting__label {font-size:.72rem;letter-spacing:.05em;text-transform:uppercase;color:#777b81;font-weight:750;margin-bottom:.3rem;}
          .provider-note {border:1px solid #e4e7eb;border-radius:1rem;padding:1rem 1.05rem;margin:.7rem 0 1rem;background:#fff;}
          .provider-note strong {display:block;margin-bottom:.2rem;}
          [data-testid="stForm"] {border:0!important;padding:0!important;}
          [data-testid="stForm"] [data-testid="InputInstructions"] {display:none!important;}
          @media (max-width:640px) {
            .connection-title {font-size:1.4rem;}
            .block-container, [data-testid="stMainBlockContainer"] {padding:2rem 1rem 3rem!important;}
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    top_left, top_middle, top_right = st.columns([1, 3, 1])
    with top_left:
        if st.button("Back", width="stretch", icon=":material/arrow_back:"):
            st.session_state.screen = (
                "home"
                if st.session_state.connect_return == "generate"
                else st.session_state.connect_return
            )
            st.session_state.connection_error = None
            st.rerun()
    with top_middle:
        st.markdown(_doodle_logo("compact", centred=True), unsafe_allow_html=True)
    with top_right:
        st.empty()

    st.markdown(
        '<div class="connection-title">Connect an image generator</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="connection-subtitle">One key lets Doodle turn your description into a printable picture. You only do this once.</div>',
        unsafe_allow_html=True,
    )

    idea = str(st.session_state.get("generation_idea", "")).strip()
    if idea and st.session_state.get("connect_return") == "generate":
        st.markdown(
            '<div class="idea-waiting"><div class="idea-waiting__label">Your idea is waiting</div></div>',
            unsafe_allow_html=True,
        )
        st.write(idea)

    active_id = str(st.session_state.get("provider_choice") or _active_provider_id())
    active_id = active_id if active_id in PROVIDERS else DEFAULT_PROVIDER
    labels = [spec.label for spec in PROVIDERS.values()]
    current_index = list(PROVIDERS).index(active_id)
    chosen_label = st.radio(
        "Choose a provider",
        labels,
        index=current_index,
        horizontal=True,
        help="You can switch provider later without changing your saved Doodles.",
    )
    provider_id = provider_id_from_label(chosen_label)
    st.session_state.provider_choice = provider_id
    spec = get_provider(provider_id)

    st.markdown(
        f'<div class="provider-note"><strong>{spec.label}</strong>{spec.description}<br><span class="small-muted">{spec.billing_note}</span></div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="step-label">Step 1 · Create a provider key</div>',
        unsafe_allow_html=True,
    )
    link_a, link_b = st.columns(2)
    with link_a:
        st.link_button(
            f"Open {spec.label} API keys",
            spec.key_url,
            width="stretch",
            icon=":material/open_in_new:",
        )
    with link_b:
        st.link_button(
            spec.billing_button_label,
            spec.billing_url,
            width="stretch",
            icon=":material/open_in_new:",
        )

    st.caption(spec.setup_hint)

    connection_error = st.session_state.get("connection_error")
    if connection_error and str(connection_error.get("provider", "")).lower() in {
        "",
        spec.label.lower(),
    }:
        st.error(str(connection_error.get("message", "The connection failed.")))
        code = str(connection_error.get("code", ""))
        if code == "billing":
            st.info(
                "The key may be valid, but the provider has no usable API balance or billing method."
            )
        elif code == "verification":
            st.info(
                "Finish the provider's account verification, then try the same key again."
            )

    existing_key, existing_source = _provider_key(provider_id)
    replacing = bool(st.session_state.get("connect_replace"))

    if existing_key and not replacing:
        st.markdown(
            '<div class="step-label">Step 2 · Confirm the connection</div>',
            unsafe_allow_html=True,
        )
        st.success(
            f"{spec.label} is connected using {mask_key(existing_key)} ({existing_source})."
        )
        use_col, replace_col = st.columns(2)
        with use_col:
            if st.button(
                "Use this connection"
                if st.session_state.connect_return != "generate"
                else "Use this connection & draw",
                type="primary",
                width="stretch",
            ):
                _set_active_provider(provider_id)
                _continue_after_connection()
        with replace_col:
            if st.button("Replace key", width="stretch"):
                st.session_state.connect_replace = True
                st.rerun()

        if existing_source != get_provider(provider_id).env_var:
            if st.button("Disconnect this provider", width="stretch"):
                session_keys = dict(st.session_state.get("session_provider_keys", {}))
                session_keys.pop(provider_id, None)
                st.session_state.session_provider_keys = session_keys
                delete_provider_key(provider_id)
                st.session_state.connect_replace = True
                st.session_state.connection_error = None
                st.rerun()
        else:
            st.caption(
                f"This key comes from the {spec.env_var} environment variable. Remove it in Terminal to disconnect it."
            )
    else:
        st.markdown(
            '<div class="step-label">Step 2 · Paste the key</div>',
            unsafe_allow_html=True,
        )
        with st.form(f"connect_{provider_id}", clear_on_submit=False):
            pasted_key = st.text_input(
                f"{spec.label} API key",
                type="password",
                placeholder=spec.key_placeholder,
                help="Doodle never writes this key into artwork, PDFs or the Git repository.",
            )
            remember_key = st.checkbox("Remember on this Mac", value=True)
            # The step number belongs to the heading above, not to the button.
            submit_label = (
                "Connect and draw"
                if st.session_state.connect_return == "generate"
                else "Connect"
            )
            connect_clicked = st.form_submit_button(
                submit_label,
                type="primary",
                width="stretch",
                icon=":material/link:",
            )

        with st.expander("Where is my key stored?"):
            st.caption(
                f"Doodle stores remembered keys only on this computer at {data_root() / 'credentials.json'}, "
                "with user-only file permissions. The file is outside the repository and excluded by Git."
            )

        if connect_clicked:
            key = pasted_key.strip()
            if not key:
                st.session_state.connection_error = {
                    "message": "Paste the API key you just created.",
                    "code": "missing_key",
                    "provider": spec.label,
                }
                st.rerun()
            try:
                with st.spinner(f"Checking {spec.label}…"):
                    check = check_provider_connection(provider_id, key)
                credits = check.get("credits")
                if provider_id == "recraft" and credits is not None:
                    try:
                        credit_balance = float(credits)
                    except (TypeError, ValueError):
                        credit_balance = None
                    if credit_balance is not None and credit_balance <= 0:
                        raise GeneratorError(
                            "Recraft is connected, but the API-unit balance is zero.",
                            provider="Recraft",
                            code="billing",
                        )
            except GeneratorError as exc:
                st.session_state.connection_error = _provider_connection_message(exc)
                st.rerun()

            session_keys = dict(st.session_state.get("session_provider_keys", {}))
            session_keys[provider_id] = key
            st.session_state.session_provider_keys = session_keys
            if remember_key:
                save_provider_key(provider_id, key)
            elif replacing:
                delete_provider_key(provider_id)
            _set_active_provider(provider_id)
            st.session_state.connection_error = None
            _continue_after_connection()

    st.divider()
    if st.button("Try Doodle with a sample picture instead", width="stretch"):
        st.session_state.quick_mode = "demo"
        st.session_state.generation_nonce = 0
        st.session_state.screen = "generate"
        st.session_state.connection_error = None
        st.rerun()
    st.caption(
        "The sample tests the complete print flow, but it will not match the description you entered."
    )


def _resolve_cast(character_ids) -> list[tuple[str, str, str, str, str]]:
    """Wiring only: resolve_cast (colouring_factory.characters) is the pure
    lookup; this just supplies it with the cached cast rather than reading
    from disk directly."""

    return resolve_cast(character_ids, _characters())


def _cast_for_drawing() -> list[tuple[str, str, str, str, str]]:
    """The ticked ids, resolved against who is actually still saved."""

    return _resolve_cast(st.session_state.get("chosen_characters", []))


def _recorded_cast() -> list[tuple[str, str, str, str, str]]:
    """Who a doodle was actually drawn with, not who is ticked now.

    _quick_generate records the cast a scene was drawn with on the artwork's
    own metadata, under "generation" -> "characters". Reading that back here,
    rather than the live tick list _cast_for_drawing reads, is what stops a
    redraw putting a character into a picture — a sample, or an ordinary
    idea drawn with no cast at all — that never had them. A picture drawn
    without a recorded cast falls back to none, whatever is ticked now.
    """

    recorded_ids = (
        st.session_state.get("current_metadata", {})
        .get("generation", {})
        .get("characters", [])
    )
    return _resolve_cast(recorded_ids)


def _current_generation_idea() -> str:
    idea = str(st.session_state.get("generation_idea", "")).strip()
    if not idea:
        raise GeneratorError(
            "Describe what Doodle should draw first.", code="missing_prompt"
        )
    return idea


def _quick_generate_demo(idea: str) -> None:
    """The built-in-sample path: one picture, chosen from disk, no charge.

    Drawn in a single call with no stop button, unlike the AI path below:
    there is nothing paid in flight to stop, and nothing already drawn to
    keep if a parent changed their mind partway through.
    """

    demos = list(list_demo_artwork().items())
    nonce = int(st.session_state.get("generation_nonce", 0))
    index = int(
        hashlib.sha256(f"{idea}|{nonce}".encode("utf-8")).hexdigest()[:8], 16
    ) % len(demos)
    demo_name, demo_path = demos[index]
    raw = demo_path.read_bytes()
    _set_current_artwork(
        raw,
        title=idea,
        metadata={
            "source": "Built-in sample",
            "sample": demo_name,
            "concept": idea,
        },
    )
    # A chain left over from an earlier picture would otherwise still be
    # what the change box and badge redraw act on.
    sample = GeneratedArtwork(
        image_bytes=raw,
        prompt=idea,
        provider="Built-in sample",
        model=demo_name,
        metadata={"sample": demo_name, "concept": idea},
    )
    _start_version_chain(sample)
    st.session_state.candidates = []
    _prepare_quick_outputs()
    _prepare_pair_outputs()


def _quick_wanted_count() -> int:
    """How many pictures this batch will draw, before the plan exists.

    Known from the settings alone: pairing always draws exactly two
    (the children's sheet and the grown-up one), whatever the alternatives
    count says, and otherwise it is that count directly. Used only to show
    a true "drawing 1 of N" on the very first render, before
    _build_generation_plan has resolved the actual list of jobs.
    """

    options = quick_drawing_options(load_settings())
    return 2 if options["pair_grown_up"] else int(options["alternatives"])


def _clear_generation_plan() -> None:
    """Forget an in-progress or finished batch's plan and any pictures kept.

    Called whenever the generate screen stops for good — the batch finished,
    the parent stopped it, or it failed — so the next visit always starts
    from a fresh plan rather than quietly continuing a stale one.
    """

    st.session_state.generation_jobs = []
    st.session_state.generation_collected = []
    st.session_state.generation_seconds = []
    st.session_state.generation_uses_cast = False
    st.session_state.generation_references = ()
    st.session_state.generation_chosen_ids = []
    st.session_state.generation_pairing = False
    st.session_state.generation_random_seed_base = 0
    st.session_state.generation_stop_requested = False


def _build_generation_plan(idea: str) -> None:
    """One-time setup for a batch: which pictures to draw, and their prompts.

    Everything here used to happen inside one call that then drew the whole
    batch in the same breath. Splitting the plan out means each picture can
    be drawn on its own script run — see _draw_next_quick_picture — with the
    page coming back to life, stop button and all, between each one.
    """

    provider_id = _active_provider_id()
    spec = get_provider(provider_id)
    api_key, _source = _provider_key(provider_id)
    if not api_key:
        raise GeneratorError(
            f"Connect {spec.label} before generating artwork.",
            provider=spec.label,
            code="missing_key",
        )

    settings = load_settings()
    options = quick_drawing_options(settings)
    pairing = bool(options["pair_grown_up"])
    wanted = 1 if pairing else int(options["alternatives"])

    # One alternative needs no plan: the brief exists to pull several
    # drawings of one idea apart from each other. A pair is the opposite
    # errand, one scene drawn twice, so it never asks for briefs either.
    briefs = [""]
    if wanted > 1:
        briefs = list(
            build_variation_briefs(
                idea, wanted, provider_id=provider_id, api_key=api_key
            )
        )

    levels = [str(options["age_profile"])] * len(briefs)
    if pairing:
        # The same words describe the scene both times, so the two sheets
        # show the same picture and only the drawing rules differ. True
        # whether or not a cast is chosen: pairing is one scene drawn at
        # two detail levels, never two different scenes.
        levels.append(GROWN_UP_LEVEL)
        briefs.append(briefs[0])

    chosen = _cast_for_drawing()
    if chosen:
        # A character drawing goes through refine_with_provider, the call
        # that carries pictures, rather than generate_with_provider. The
        # reference sent is the stored photograph, not the drawn portrait:
        # the portrait is a deliberate caricature, and sending it as the
        # likeness reference would draw every scene from that exaggeration
        # rather than from the child or toy it was drawn from.
        # The portrait, not the photograph. The library shows the parent
        # this drawing, so it is what the scene has to agree with; drawing
        # from the photograph instead produced a second reading of the same
        # face that was close but not the same child.
        references = tuple(
            load_character_image(character_id, portrait=True)
            for character_id, *_ in chosen
        )
        prompts = [
            build_character_scene_prompt(
                idea,
                [
                    (name, kind, marks, appearance)
                    for _, name, kind, marks, appearance in chosen
                ],
                age_profile=level,
                style_name=str(options["style"]),
                target="A4 page",
                variation_brief=brief,
            )
            for level, brief in zip(levels, briefs)
        ]
    else:
        references = ()
        prompts = [
            build_colouring_prompt(
                idea,
                age_profile=level,
                style_name=str(options["style"]),
                target="A4 page",
                extra_instructions="One clear subject or action, generous white space, no caption or text.",
                variation_brief=brief,
            )
            for level, brief in zip(levels, briefs)
        ]

    nonce = int(st.session_state.get("generation_nonce", 0))
    random_seed_base = int(
        hashlib.sha256(f"{idea}|{nonce}".encode("utf-8")).hexdigest()[:8], 16
    )

    st.session_state.generation_jobs = [
        {"prompt": prompt, "level": level, "brief": brief}
        for prompt, level, brief in zip(prompts, levels, briefs)
    ]
    st.session_state.generation_collected = []
    st.session_state.generation_seconds = []
    st.session_state.generation_uses_cast = bool(chosen)
    st.session_state.generation_references = references
    st.session_state.generation_chosen_ids = [
        character_id for character_id, *_ in chosen
    ]
    st.session_state.generation_pairing = pairing
    st.session_state.generation_random_seed_base = random_seed_base


def _draw_next_quick_picture(job_index: int) -> GeneratedArtwork:
    """Draw exactly one picture from the frozen plan: one paid call.

    Whichever provider is connected, generate_with_provider and
    refine_with_provider each make one request per prompt they are handed,
    so passing a single-item prompt list is what keeps this to one call.
    """

    provider_id = _active_provider_id()
    spec = get_provider(provider_id)
    api_key, _source = _provider_key(provider_id)
    settings = load_settings()
    model = _model_for(provider_id, spec, settings)
    # Medium rather than low: low quality renders more fine detail as pale
    # grey that the black/white pass then breaks up.
    quality = str(settings.get("openai_quality", DEFAULT_QUALITY))

    job = st.session_state.generation_jobs[job_index]
    chosen_ids = list(st.session_state.generation_chosen_ids)

    started = time.monotonic()
    if st.session_state.generation_uses_cast:
        artwork = refine_with_provider(
            provider_id=provider_id,
            api_key=api_key,
            prompt=job["prompt"],
            reference_images=st.session_state.generation_references,
            model=model,
            size=spec.portrait_size,
            quality=quality,
        )
    else:
        # Advances the seed by this job's position, the same offset
        # generate_with_provider's own per-prompt loop would have applied
        # had the whole batch still been handed to it as one list.
        random_seed = int(st.session_state.generation_random_seed_base) + job_index
        artworks = generate_with_provider(
            provider_id=provider_id,
            api_key=api_key,
            prompts=[job["prompt"]],
            model=model,
            size=spec.portrait_size,
            quality=quality,
            random_seed=random_seed,
        )
        artwork = artworks[0]

    # Timed around the paid call alone. Timing the whole script run would fold
    # in the planning call that only the first picture of a batch carries and
    # the two PDF builds only the last one carries, and neither is time spent
    # waiting for this picture. Recorded before anything below can raise, so a
    # slow drawing still teaches the next wait what to expect.
    drawn_in = time.monotonic() - started
    record_timing(
        seconds=drawn_in,
        settings_key=settings_key(
            provider=provider_id,
            model=model,
            quality=quality,
            size=spec.portrait_size,
            with_references=bool(st.session_state.generation_uses_cast),
        ),
    )
    st.session_state.generation_seconds = [
        *st.session_state.get("generation_seconds", []),
        drawn_in,
    ]

    artwork.metadata["brief"] = job["brief"]
    artwork.metadata["detail_level"] = job["level"]
    # Recorded so a later badge redraw draws whoever was actually in this
    # picture, never whoever happens to be ticked when that button is
    # pressed — see _recorded_cast.
    artwork.metadata["characters"] = chosen_ids
    return artwork


def _finish_quick_generation() -> None:
    """Adopt whatever has been drawn and land on the result screen.

    Called both when a batch finishes on its own and when a parent stops it
    partway through: either way, whatever is in generation_collected is
    everything that gets kept, exactly as if that many had been asked for.
    """

    idea = str(st.session_state.get("generation_idea", ""))
    collected = list(st.session_state.get("generation_collected") or [])
    jobs = st.session_state.get("generation_jobs") or []
    pairing = bool(st.session_state.get("generation_pairing"))
    chosen_ids = list(st.session_state.get("generation_chosen_ids") or [])

    for_children, grown_up = split_pairing_results(
        collected, pairing=pairing, total_jobs=len(jobs)
    )

    st.session_state.candidates = for_children if len(for_children) > 1 else []
    _adopt_artwork(for_children[0], idea, characters=chosen_ids)
    st.session_state.pair_raw = grown_up.image_bytes if grown_up else None

    _clear_generation_plan()
    _prepare_quick_outputs()
    _prepare_pair_outputs()
    st.session_state.screen = "result"


def _prepare_quick_outputs() -> None:
    """Clean the current picture and build its A4 PDF."""

    # Take the tuned defaults rather than repeating them. A copied number here
    # was quietly undoing the threshold set everywhere else, on the very first
    # picture a new user sees.
    quick_defaults = ProcessingOptions(despeckle_size=3)
    processed = _cached_process(
        st.session_state.current_raw,
        quick_defaults.threshold,
        quick_defaults.auto_invert,
        quick_defaults.crop_whitespace,
        quick_defaults.padding_percent,
        quick_defaults.despeckle_size,
        quick_defaults.thicken_pixels,
    )
    config = FullPageConfig(
        page_width_mm=210.0,
        page_height_mm=297.0,
        margin_mm=12.0,
        caption="",
        caption_font_size_pt=17.0,
        caption_area_mm=27.0,
    )
    st.session_state.quick_processed = processed
    st.session_state.quick_pdf = create_full_page_pdf(processed, config)
    st.session_state.quick_saved = False


A4_SHEET = FullPageConfig(
    page_width_mm=210.0,
    page_height_mm=297.0,
    margin_mm=12.0,
    caption="",
    caption_font_size_pt=17.0,
    caption_area_mm=27.0,
)

BADGE_58MM = CircleSheetConfig(
    finished_diameter_mm=58.0, cut_diameter_mm=58.0, safe_diameter_mm=50.0
)


def _prepare_pair_outputs() -> None:
    """Clean the grown-up sheet, gently, and build its A4 PDF.

    The despeckle pass that tidies stray pixels out of a toddler drawing eats
    the fine pattern work a grown-up sheet exists for, and thickening lines
    closes its smallest regions up altogether. Both are turned down here.
    """

    raw = st.session_state.get("pair_raw")
    if not raw:
        st.session_state.pair_processed = None
        st.session_state.pair_pdf = None
        return

    fine = ProcessingOptions(despeckle_size=1, thicken_pixels=0)
    processed = _cached_process(
        raw,
        fine.threshold,
        fine.auto_invert,
        fine.crop_whitespace,
        fine.padding_percent,
        fine.despeckle_size,
        fine.thicken_pixels,
    )
    st.session_state.pair_processed = processed
    st.session_state.pair_pdf = create_full_page_pdf(processed, A4_SHEET)


def _render_grown_up_sheet() -> None:
    """The matching intricate sheet, when one was drawn.

    Everything above it acts on the children's sheet, which is the one being
    changed, coloured in and saved. This is the second print, and it is left
    exactly as it was drawn.
    """

    pdf_bytes = st.session_state.get("pair_pdf")
    processed = st.session_state.get("pair_processed")
    if not pdf_bytes or not processed:
        return

    with st.container(border=True):
        st.markdown("**Your sheet**")
        st.caption(
            "The same scene drawn for a grown-up, so you can colour along with "
            "them. Print both and share the pencils."
        )
        st.image(processed, width="stretch")
        if st.button(
            "Print your sheet",
            type="primary",
            width="stretch",
            icon=":material/print:",
            key="print_grown_up",
        ):
            _send_to_printer(pdf_bytes)
        _render_print_help(
            pdf_bytes,
            file_name=f"{_slug(st.session_state.current_title)}-grown-up-a4.pdf",
            key="grown_up",
            scale_note=False,
        )


# TARGET_RULES["Round badge"] already asks for a square, corners-empty
# composition, but naming the crop explicitly is what actually keeps a model
# from filling the corners anyway — the same lesson BADGE_CORNERS_RULE
# records for the caricature prompt.
_BADGE_REDRAW_EXTRA_INSTRUCTIONS = (
    "This picture will be cut into a circle to make a badge, so keep the "
    "four corners empty and fill the frame with one clear subject."
)


def _render_badge_strip() -> None:
    """Every finished doodle, already fitted to a 58 mm badge for free.

    Keyed by a hash of the picture actually on screen, the same shape
    colour_previews already uses for the coloured-copy cache: a redraw, a
    refinement or a swapped alternative all just change quick_processed, and
    whatever that now is gets looked up (or computed and cached) fresh here.
    Nothing has to remember to call a separate "keep the badge in sync"
    function, so no path can leave a stale one behind.
    """

    processed = st.session_state.get("quick_processed")
    if not processed:
        return

    # Read once per run, whether or not the preview cache hits: the badge
    # sheet built below needs the same profile, and loading it only on a
    # cache miss left it undefined the rest of the time.
    calibration = CalibrationProfile.from_dict(load_settings().get("calibration"))

    cache = st.session_state.setdefault("badge_previews", {})
    key = _colour_key(processed)
    preview = cache.get(key)
    if preview is None:
        preview = _cached_badge_preview(
            processed,
            json.dumps(asdict(BADGE_58MM), sort_keys=True),
            json.dumps(calibration.to_dict(), sort_keys=True),
        )
        cache[key] = preview

    provider_id = _active_provider_id()
    spec = get_provider(provider_id)
    api_key, _source = _provider_key(provider_id)

    with st.container(border=True):
        st.markdown("**Your badge**")
        st.image(preview, width="stretch")
        st.caption(
            "Your doodle fitted to a 58 mm badge. Doodle can draw it again "
            "composed for the circle instead, which costs one generation."
        )
        if st.button(
            "Draw it for a badge",
            width="stretch",
            icon=":material/badge:",
            key="draw_for_badge",
            disabled=not api_key,
        ) and not _drawing_already_in_flight("busy_badge"):
            idea = (
                str(
                    st.session_state.get("current_metadata", {}).get("concept")
                    or st.session_state.get("current_title", "")
                ).strip()
                or "Doodle"
            )
            settings = load_settings()
            options = quick_drawing_options(settings)
            model = _model_for(provider_id, spec, settings)
            quality = str(settings.get("openai_quality", DEFAULT_QUALITY))
            # The cast this doodle was actually drawn with, not whoever is
            # ticked right now: ticking someone after the fact must not put
            # them into a picture — a sample, or an ordinary idea drawn
            # with no cast — that never had them.
            chosen = _recorded_cast()

            try:
                with _mark_in_flight("busy_badge"):
                    with st.spinner("Composing it for a badge…"):
                        if chosen:
                            # The same portrait the scene was drawn from,
                            # so a badge of your daughter is the same girl as
                            # the page it was cut from.
                            references = tuple(
                                load_character_image(character_id, portrait=True)
                                for character_id, *_ in chosen
                            )
                            artwork = refine_with_provider(
                                provider_id=provider_id,
                                api_key=api_key,
                                prompt=build_character_scene_prompt(
                                    idea,
                                    [
                                        (name, kind, marks, appearance)
                                        for _, name, kind, marks, appearance in chosen
                                    ],
                                    age_profile=str(options["age_profile"]),
                                    style_name=str(options["style"]),
                                    target="Round badge",
                                    extra_instructions=_BADGE_REDRAW_EXTRA_INSTRUCTIONS,
                                ),
                                reference_images=references,
                                model=model,
                                size=spec.square_size,
                                quality=quality,
                            )
                        else:
                            artworks = generate_with_provider(
                                provider_id=provider_id,
                                api_key=api_key,
                                prompts=[
                                    build_colouring_prompt(
                                        idea,
                                        age_profile=str(options["age_profile"]),
                                        style_name=str(options["style"]),
                                        target="Round badge",
                                        extra_instructions=_BADGE_REDRAW_EXTRA_INSTRUCTIONS,
                                    )
                                ],
                                model=model,
                                size=spec.square_size,
                                quality=quality,
                            )
                            artwork = artworks[0]
            except GeneratorError as exc:
                _show_guidance(exc.code, detail=str(exc))
            else:
                st.session_state.candidates = []
                _adopt_artwork(
                    artwork,
                    idea,
                    characters=[character_id for character_id, *_ in chosen],
                )
                _prepare_quick_outputs()
                st.rerun()

        # The strip previewed a badge and, above, can charge a generation to
        # compose one, so it has to be able to produce an actual badge too:
        # the same circle-sheet layout Doodle Studio's "A4 circle sheet"
        # export uses, at the 58 mm size this strip already advertises.
        sheet_pdf = _cached_badge_sheet_pdf(
            processed,
            json.dumps(asdict(BADGE_58MM), sort_keys=True),
            json.dumps(calibration.to_dict(), sort_keys=True),
        )
        st.caption("An A4 sheet of these badges, ready to cut out.")
        if st.button(
            "Print your badges",
            type="primary",
            width="stretch",
            icon=":material/print:",
            key="print_badges",
        ):
            _send_to_printer(sheet_pdf)
        _render_print_help(
            sheet_pdf,
            file_name=f"{_slug(st.session_state.current_title)}-58mm-badges.pdf",
            key="badges",
            scale_note=False,
        )


# A failure about the picture or the cast Doodle was asked to draw, not
# about the connection: routing these to the Connect screen showed "such-
# and-such is connected" next to a message naming no provider at all, and
# on a provider the Connect screen's stale-provider filter did not match
# (Google Gemini, reached only through this feature's reference-image
# call), the parent was moved there with nothing shown at all.
_PICTURE_OR_CAST_CODES = frozenset(
    {
        "content",
        "missing_prompt",
        "photo_declined",
        "too_many_references",
        "no_reference_support",
        "missing_picture",
    }
)


def _route_generation_failure(exc: GeneratorError) -> None:
    """Send a failed drawing attempt to the screen its kind of failure needs.

    A failure about the picture or the cast Doodle was asked to draw, not
    about the connection: routing these to the Connect screen showed "such-
    and-such is connected" next to a message naming no provider at all, and
    on a provider the Connect screen's stale-provider filter did not match
    (Google Gemini, reached only through this feature's reference-image
    call), the parent was moved there with nothing shown at all.
    """

    provider_id = _active_provider_id()
    _key, source = _provider_key(provider_id)
    if exc.code in _PICTURE_OR_CAST_CODES:
        st.session_state.home_error = str(exc)
        st.session_state.home_error_code = exc.code
        st.session_state.home_prompt = st.session_state.generation_idea
        st.session_state.screen = "home"
    else:
        st.session_state.home_error_code = ""
        st.session_state.connection_error = _provider_connection_message(exc)
        st.session_state.connect_return = "generate"
        st.session_state.connect_replace = exc.code in {
            "authentication",
            "permission",
        }
        if exc.code == "authentication":
            session_keys = dict(st.session_state.get("session_provider_keys", {}))
            session_keys.pop(provider_id, None)
            st.session_state.session_provider_keys = session_keys
            if source == "this Mac":
                delete_provider_key(provider_id)
        st.session_state.screen = "connect"


def _route_generation_value_error(exc: ValueError) -> None:
    # Undecodable image bytes, or artwork the layout cannot place. Without
    # this the user sees a traceback and the screen stays on "generate", so
    # every rerun fires another paid generation.
    st.session_state.home_error = (
        f"That picture could not be prepared for printing: {exc}"
    )
    st.session_state.home_error_code = ""
    st.session_state.home_prompt = st.session_state.generation_idea
    st.session_state.screen = "home"


def _stop_quick_generation() -> None:
    """Handle a press of Stop: keep whatever is drawn, or go home with
    nothing lost if nothing has been drawn yet.

    The request already sent for the picture in flight, if any, still
    finishes and is still charged — this only stops the ones after it, by
    never starting them.
    """

    if st.session_state.get("generation_collected"):
        _finish_quick_generation()
        return
    st.session_state.home_prompt = st.session_state.get("generation_idea", "")
    st.session_state.screen = "home"
    _clear_generation_plan()


def _keep_partial_batch_progress(message: str) -> bool:
    """A failure partway through a batch should keep what already
    succeeded, the way a parent-pressed Stop does — those pictures were
    already drawn and already charged for. Returns False, doing nothing,
    when nothing has been collected yet: there is nothing to keep, so the
    caller falls through to its usual failure routing unchanged.
    """

    if not st.session_state.get("generation_collected"):
        return False
    done = len(st.session_state.generation_collected)
    total = len(st.session_state.get("generation_jobs") or [])
    st.session_state.generation_notice = (
        f"Doodle drew {done} of the {total} pictures you asked for; the "
        f"rest could not be drawn: {message} What worked is ready below."
    )
    _finish_quick_generation()
    return True


# Every keyframe name carries __I__, replaced with the picture's index, for
# the reason given in _waiting_chart_html. `width:100%` beside the max-width
# rather than relying on the auto margins alone: an automatic cross-axis margin
# on a flex child cancels the stretch that gives it its width, and the bars
# then share out nothing between them.
_WAITING_CHART_CSS = """
  .wait-hist{width:100%;max-width:520px;margin:1.15rem auto .2rem}
  .wait-hist__bars{display:flex;align-items:flex-end;gap:4px;height:104px;padding-top:6px}
  .wait-hist__bars i{
    flex:1 1 0;min-width:0;min-height:10px;
    border-radius:10px 10px 4px 4px;
    background:#fff;border:2.5px solid #e6e9ee;
    display:block;box-sizing:border-box;
    animation:wait-fill-__I__ 5s ease-out forwards;
    animation-delay:calc(var(--i) * 5s);
  }
  @keyframes wait-fill-__I__{
    0%{background:#fff;border-color:#e6e9ee;transform:translateY(0)}
    8%{background:var(--c);border-color:var(--c);transform:translateY(-6px)}
    56%{background:var(--c);border-color:var(--c);transform:translateY(-6px)}
    100%{background:var(--c);border-color:var(--c);transform:translateY(0)}
  }
  .wait-hist__bars i:nth-child(6n+1){--c:#4f46e5}
  .wait-hist__bars i:nth-child(6n+2){--c:#f45b69}
  .wait-hist__bars i:nth-child(6n+3){--c:#f5a623}
  .wait-hist__bars i:nth-child(6n+4){--c:#16a085}
  .wait-hist__bars i:nth-child(6n+5){--c:#8b5cf6}
  .wait-hist__bars i:nth-child(6n){--c:#0ea5e9}
  .wait-hist__rail{position:relative;height:20px;margin-top:4px}
  .wait-hist__spark{
    position:absolute;top:0;left:0;width:calc((100% + 4px)/18);
    text-align:center;line-height:1;font-family:Georgia,serif;
    font-size:1.15rem;color:#f5a623;
    animation:wait-spark-__I__ 90s steps(18,end) forwards;
  }
  @keyframes wait-spark-__I__{to{transform:translateX(1800%)}}
  .wait-hist__axis{display:flex;font-size:.72rem;color:#a9adb5;margin-top:-4px}
  .wait-hist__axis span{flex:1;text-align:center}
  .wait-hist__axis span:first-child{text-align:left}
  .wait-hist__axis span:last-child{text-align:right}
  .wait-hist__cap{
    font-size:.82rem;color:#8a8e94;margin:.55rem auto 0;
    max-width:420px;line-height:1.45;
  }
  /* Opening from no height at all, so a note that has not fired yet leaves no
     reserved gap under the chart waiting to be filled. */
  .wait-note{
    opacity:0;max-height:0;overflow:hidden;
    color:#8a4a3f;font-size:.86rem;max-width:440px;margin:0 auto;line-height:1.45;
    animation:wait-note-__I__ .45s ease forwards;
  }
  @keyframes wait-note-__I__{
    from{opacity:0;max-height:0}
    to{opacity:1;max-height:7rem}
  }
  .wait-note--slow{animation-delay:__SLOWEST__s}
  .wait-note--stuck{animation-delay:240s}
  /* The marching is information rather than decoration, so it keeps going for
     a reader who asks for less motion; only the bounce is dropped. */
  @media (prefers-reduced-motion: reduce){
    @keyframes wait-fill-__I__{
      0%{background:#fff;border-color:#e6e9ee}
      8%,100%{background:var(--c);border-color:var(--c)}
    }
  }
"""


def _current_settings_key() -> str:
    """What makes this drawing comparable with past ones."""

    provider_id = _active_provider_id()
    spec = get_provider(provider_id)
    settings = load_settings()
    return settings_key(
        provider=provider_id,
        model=_model_for(provider_id, spec, settings),
        quality=str(settings.get("openai_quality", DEFAULT_QUALITY)),
        size=spec.portrait_size,
        with_references=bool(st.session_state.get("generation_uses_cast")),
    )


def _waiting_chart_html(job_index: int) -> str:
    """Past drawings as a distribution, with a marker that walks along it.

    Every bit of movement here is CSS. While a picture is being drawn the
    script is inside a network call and sends the browser nothing at all, so a
    bar that lights every five seconds has to be a keyframe with a delay per
    bar; anything that asks Python for the time would sit frozen with the rest
    of the page. A bar ahead of the marker is an empty outline, the way a shape
    on an uncoloured page is, and fills in as the marker reaches it.

    Every keyframe name carries the picture's index. The markup is otherwise
    identical between pictures of a batch, so the browser would reuse the old
    animation timeline and picture two would open with its chart already
    coloured in and its "taking a while" note already showing.
    """

    durations = durations_for(load_timings(), _current_settings_key())
    if len(durations) < MIN_RECORDS_FOR_CHART:
        return ""

    counts = histogram(durations)
    heights = bar_heights(counts, tallest_px=104, floor_px=10)
    slowest = max(durations)

    bars = "".join(
        f'<i style="--i:{index};height:{height}px"></i>'
        for index, height in enumerate(heights)
    )
    caption = (
        f"Your last {len(durations)} drawings at these settings, "
        "and where this one has got to."
    )

    css = _WAITING_CHART_CSS.replace("__I__", str(job_index))
    css = css.replace("__SLOWEST__", f"{slowest:.0f}")
    return (
        f"<style>{css}</style>"
        f'<div class="wait-hist" aria-hidden="true">'
        f'<div class="wait-hist__bars">{bars}</div>'
        f'<div class="wait-hist__rail"><div class="wait-hist__spark">\u2726</div></div>'
        f'<div class="wait-hist__axis"><span>straight away</span>'
        f"<span>45 seconds</span><span>a minute and a half</span></div>"
        f"</div>"
        f'<div class="wait-hist__cap">{html.escape(caption)}</div>'
        f'<div class="wait-note wait-note--slow">This one is taking longer than '
        f"any of those. It is still going, and the screen will move on by "
        f"itself.</div>"
        f'<div class="wait-note wait-note--stuck">Doodle allows four minutes for '
        f"each attempt and then tries again, up to three attempts in all. It "
        f"will say what happened rather than sitting here.</div>"
    )


def _render_generating_screen() -> None:
    st.markdown(
        """
        <style>
          [data-testid="stHeader"], [data-testid="stToolbar"],
          [data-testid="collapsedControl"], [data-testid="stSidebar"] {display:none!important;}
          /* Every declaration here is marked important, including the ones
             that look as though they should not need it. Streamlit's own
             stylesheet outranks a plain declaration on this container, so this
             screen kept the 650px width that was marked and silently lost the
             centring and the full height that were not: everything rendered
             hard against the left edge with white space below it. */
          .block-container, [data-testid="stMainBlockContainer"] {
            max-width:650px!important;
            min-height:100dvh!important;
            padding:3rem 1.25rem 5rem!important;
            display:flex!important;
            flex-direction:column!important;
            justify-content:center!important;
            text-align:center!important;
            overflow:visible!important;
          }
          .drawing-title{font-size:1.35rem;font-weight:760;margin:.8rem 0 .35rem;}
          /* The child's own sentence, promoted from a grey caption to the
             largest words on the screen. She is the one standing here waiting
             for it, and she can hear it read back. */
          .drawing-idea{
            font-size:1.5rem;font-weight:720;color:#171717;
            max-width:520px;margin:0 auto 1.1rem;line-height:1.3;
          }
          .drawing-label{
            font-size:.73rem;font-weight:760;letter-spacing:.055em;color:#73777d;
            text-transform:uppercase;margin:.1rem 0 .35rem;
          }
          .drawing-progress{color:#676b70;font-weight:600;margin:0 0 .15rem;}
          /* Six shapes, one every eight tenths of a second, each rotated by
             the same angle as the matching letter of the wordmark so the reel
             reads as this app's rather than as a stock loader. Three of them
             are PlayStation face buttons, which was the reference asked for.
             The cross is left out on purpose: a cross reads as an error. */
          /* The six shapes sit on top of one another and take turns being
             visible, rather than scrolling past a window. The scrolling version
             clipped: a step of 2.4rem is 38.4 pixels, the window rounded to 38,
             and the error accumulated until a slice of the next shape showed
             above the current one. Stacked, there is no window to be sliced by
             and no arithmetic to drift. Each shape is centred in the box, so
             Georgia's very different glyph widths no longer make them wander
             from side to side either. */
          .drawing-reel{
            position:relative;height:44px;margin:.9rem auto .35rem;
            font-family:Georgia,serif;font-size:26px;line-height:1;
          }
          .drawing-reel span{
            position:absolute;inset:0;
            display:flex;align-items:center;justify-content:center;
            opacity:0;animation:drawing-reel 4.8s linear infinite;
          }
          @keyframes drawing-reel{
            0%,16.6%{opacity:1}
            16.7%,100%{opacity:0}
          }
          .drawing-reel span:nth-child(1){animation-delay:0s}
          .drawing-reel span:nth-child(2){animation-delay:.8s}
          .drawing-reel span:nth-child(3){animation-delay:1.6s}
          .drawing-reel span:nth-child(4){animation-delay:2.4s}
          .drawing-reel span:nth-child(5){animation-delay:3.2s}
          .drawing-reel span:nth-child(6){animation-delay:4s}
          .drawing-reel span:nth-child(1){color:#4f46e5;rotate:-4deg;}
          .drawing-reel span:nth-child(2){color:#f45b69;rotate:3deg;}
          .drawing-reel span:nth-child(3){color:#f5a623;rotate:-2deg;}
          .drawing-reel span:nth-child(4){color:#16a085;rotate:3deg;}
          .drawing-reel span:nth-child(5){color:#8b5cf6;rotate:-3deg;}
          .drawing-reel span:nth-child(6){color:#0ea5e9;rotate:2deg;}
          @media (prefers-reduced-motion: reduce){
            .drawing-reel span{animation:none;opacity:0;}
            .drawing-reel span:nth-child(1){opacity:1;}
          }
          /* The homepage's settings line answers questions this screen has
             already moved past; left on screen it renders beneath the
             spinner with Streamlit's default label clipping, since only the
             homepage carries the rules that stop that clipping. Simplest
             correct fix is to not show it here at all. */
          .st-key-doodle-home-settings {display:none!important;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(_doodle_logo("compact", centred=True), unsafe_allow_html=True)
    st.markdown(
        '<div class="drawing-title">Drawing your Doodle…</div>', unsafe_allow_html=True
    )
    st.markdown(
        '<div class="drawing-reel" aria-hidden="true">'
        "<span>\u25cb</span><span>\u25b3</span><span>\u25a1</span>"
        "<span>\u25c7</span><span>\u2726</span><span>\u2727</span>"
        "</div>",
        unsafe_allow_html=True,
    )
    safe_idea = html.escape(str(st.session_state.get("generation_idea", "")))
    st.markdown('<div class="drawing-label">Now drawing</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="drawing-idea">{safe_idea}</div>', unsafe_allow_html=True)

    is_demo = st.session_state.get("quick_mode") == "demo"

    if not is_demo:
        # Drawn one picture per script run rather than the whole batch in one
        # blocking call, so the page comes back to life between pictures with
        # a live count and a way to stop the rest — see _build_generation_plan
        # and _draw_next_quick_picture.
        jobs = st.session_state.get("generation_jobs") or []
        done = len(st.session_state.get("generation_collected") or [])
        total = len(jobs) if jobs else _quick_wanted_count()
        st.markdown(
            f'<div class="drawing-progress">Drawing {min(done + 1, total)} of {total}</div>',
            unsafe_allow_html=True,
        )
        # Left out entirely rather than drawn empty when there is too little
        # history to have a shape, because a hill of one bar reads as an
        # expectation and is not one.
        chart = _waiting_chart_html(done)
        if chart:
            st.markdown(chart, unsafe_allow_html=True)
        else:
            st.caption(
                "Doodle has not drawn at these settings before, so there is "
                "nothing yet to say how long this should take."
            )
        # Tucked behind a question mark rather than printed. It answers a
        # question a parent asks once and then knows the answer to for good,
        # and until they ask it, it is four lines of grey between the child's
        # own sentence and the button.
        with st.popover(
            "", type="tertiary", icon=":material/help:", width="content"
        ):
            st.markdown(
                "**If you stop now**\n\nA picture already sent to be drawn "
                "finishes and is charged regardless. Stopping only cancels the "
                "ones after it, and takes you straight to whatever is already "
                "drawn."
            )
        if st.button(
            "Stop drawing",
            key="stop_drawing",
            width="stretch",
            icon=":material/stop_circle:",
        ):
            st.session_state.generation_stop_requested = True
        # A plain flag rather than reading the button's own return value a
        # run later: a request already sent for the picture in flight keeps
        # running to completion regardless, so the moment that matters is
        # checked here, before the next one is ever started, not only on
        # the one run that happens to see the click itself.
        if st.session_state.get("generation_stop_requested"):
            _stop_quick_generation()
            st.rerun()
            return

    try:
        idea = _current_generation_idea()
        if is_demo:
            # No elapsed clock: this reads a picture off the disk.
            with st.spinner("Opening the sample picture…"):
                _quick_generate_demo(idea)
            st.session_state.screen = "result"
        else:
            if not st.session_state.get("generation_jobs"):
                # Its own spinner because planning several alternatives makes a
                # text-model call of its own, and it happens before the drawing
                # spinner exists — so the first thing a parent waited through
                # was the only part of the screen with nothing moving on it.
                with st.spinner("Working out what to draw…", show_time=True):
                    _build_generation_plan(idea)
            jobs = st.session_state.generation_jobs
            job_index = len(st.session_state.generation_collected)
            # show_time is Streamlit's own elapsed counter, driven by the
            # browser's clock rather than by Python, so it keeps ticking for
            # the whole blocked call. The screen rebuilds between pictures, so
            # it reads this picture rather than the batch.
            with st.spinner("Drawing the lines…", show_time=True):
                artwork = _draw_next_quick_picture(job_index)
            st.session_state.generation_collected = [
                *st.session_state.generation_collected,
                artwork,
            ]
            if len(st.session_state.generation_collected) >= len(jobs):
                _finish_quick_generation()
    except GeneratorError as exc:
        if not is_demo and _keep_partial_batch_progress(str(exc)):
            st.rerun()
            return
        if not is_demo:
            _clear_generation_plan()
        _route_generation_failure(exc)
        st.rerun()
        return
    except ValueError as exc:
        if not is_demo and _keep_partial_batch_progress(str(exc)):
            st.rerun()
            return
        if not is_demo:
            _clear_generation_plan()
        _route_generation_value_error(exc)
        st.rerun()
        return
    st.rerun()


def _how_long_that_took() -> str:
    """Confirm the number the parent just watched climb, rather than let it
    vanish the moment the picture appears. It is also the same figure that
    joins the chart on the next drawing, which is what gives the wait a small
    payoff."""

    seconds = [float(value) for value in st.session_state.get("generation_seconds") or []]
    if not seconds:
        return ""
    if len(seconds) == 1:
        return f"That took {round(seconds[0])} seconds."

    total = round(sum(seconds))
    minutes, remainder = divmod(total, 60)
    if minutes:
        spell = f"{minutes} minute{'' if minutes == 1 else 's'}"
        if remainder:
            spell += f" and {remainder} second{'' if remainder == 1 else 's'}"
    else:
        spell = f"{total} seconds"
    return f"Those {len(seconds)} took {spell} altogether."


def _render_first_result() -> None:
    st.markdown(
        """
        <style>
          [data-testid="stHeader"], [data-testid="stToolbar"],
          [data-testid="stSidebar"], [data-testid="collapsedControl"] {display:none!important;}
          .block-container,[data-testid="stMainBlockContainer"] {max-width:800px!important;padding:2.5rem 1.15rem 4rem!important;overflow:visible!important;}
          .happy-title{text-align:center;font-size:1.1rem;font-weight:720;color:#34373b;margin:.5rem 0 .15rem;}
          .happy-idea{text-align:center;font-size:.94rem;color:#777b81;margin:0 0 1.15rem;}
          [data-testid="stImage"] img{border:1px solid #e5e7eb;border-radius:1rem;background:#fff;box-shadow:0 10px 30px rgba(20,20,20,.06);}
          [data-testid="stForm"] [data-testid="InputInstructions"] {display:none!important;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    _render_top_bar(where="result")

    if st.session_state.get("generation_notice"):
        st.warning(st.session_state.generation_notice, icon=":material/info:")
        st.session_state.generation_notice = ""

    processed = st.session_state.get("quick_processed")
    if not processed:
        # Reaching here with nothing prepared is a routing mistake rather than
        # a user error, so say so plainly instead of dying on a None.
        st.error("That doodle is not ready yet. Draw it again.")
        return

    st.markdown(
        '<div class="happy-title">Your Doodle is ready</div>', unsafe_allow_html=True
    )
    safe_title = html.escape(str(st.session_state.get("current_title", "")))
    st.markdown(f'<div class="happy-idea">{safe_title}</div>', unsafe_allow_html=True)
    _render_doodle_with_colours(processed, key_prefix="result")
    took = _how_long_that_took()
    if took:
        st.caption(took)
    _render_alternatives_picker()

    again_col, love_col, print_col = st.columns([1, 1, 1.35])
    with again_col:
        if st.button(
            "Draw this idea again", width="stretch", icon=":material/refresh:"
        ):
            st.session_state.generation_nonce = (
                int(st.session_state.get("generation_nonce", 0)) + 1
            )
            st.session_state.screen = "generate"
            st.rerun()
    with love_col:
        already_saved = bool(st.session_state.get("quick_saved"))
        if already_saved:
            # A dead "Saved" button left the doodle apparently nowhere. The
            # button that replaces it is the route to where it went.
            if st.button(
                "See your saved doodles",
                width="stretch",
                icon=":material/collections_bookmark:",
            ):
                st.session_state.library_return = "result"
                st.session_state.screen = "library"
                st.rerun()
        elif st.button(
            "Save to your doodles", width="stretch", icon=":material/favorite:"
        ):
            save_library_item(
                processed_image=processed,
                raw_image=st.session_state.current_raw,
                title=st.session_state.current_title or "Doodle",
                metadata=st.session_state.current_metadata,
            )
            st.session_state.quick_saved = True
            st.rerun()
    with print_col:
        if st.button(
            "Print this doodle",
            type="primary",
            width="stretch",
            icon=":material/print:",
        ):
            _send_to_printer(st.session_state.quick_pdf)

    if st.session_state.get("quick_saved"):
        st.success("Saved to your doodles, on this computer.", icon=":material/check:")

    _render_print_help(
        st.session_state.quick_pdf,
        file_name=f"{_slug(st.session_state.current_title)}-a4.pdf",
        key="result",
    )

    _render_grown_up_sheet()
    _render_badge_strip()

    # This box used to rewrite the original idea and draw a new picture from
    # scratch. Since alternatives started coming back genuinely different, that
    # no longer returned anything like what was on screen; it now changes the
    # picture itself.
    _render_refine_controls(key_prefix="result")

    with st.expander("Other sizes & advanced options"):
        st.caption(
            "Badges, exact millimetre sizes, captions, saved artwork and printer calibration live in Doodle Studio."
        )
        studio_col, provider_col = st.columns(2)
        with studio_col:
            if st.button("Open Doodle Studio", width="stretch"):
                st.session_state.screen = "studio"
                st.rerun()
        with provider_col:
            if st.button("Change image provider", width="stretch"):
                st.session_state.connect_return = "result"
                st.session_state.connect_replace = False
                st.session_state.provider_choice = _active_provider_id()
                st.session_state.screen = "connect"
                st.rerun()


# A direct prompt should always enter the happy path. Injected artwork in tests or
# a restored session goes straight to the advanced studio.
if (
    st.session_state.current_raw is not None
    and st.session_state.screen == "home"
    and not st.session_state.home_prompt
):
    st.session_state.screen = "studio"

if st.session_state.screen == "home":
    _render_homepage()
    st.stop()
if st.session_state.screen == "connect":
    _render_connection_setup()
    st.stop()
if st.session_state.screen == "generate":
    _render_generating_screen()
    st.stop()
if st.session_state.screen == "result":
    _render_first_result()
    st.stop()
if st.session_state.screen == "characters":
    _render_characters_screen()
    st.stop()
if st.session_state.screen == "library":
    _render_library_screen()
    st.stop()

settings = load_settings()
calibration_profile = CalibrationProfile.from_dict(settings.get("calibration"))

_render_top_bar(where="studio")
st.markdown(
    '<div class="studio-subtitle">Turn an idea into a print-ready colouring page.</div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### Settings")
    studio_provider_id = _active_provider_id()
    studio_provider_labels = [spec.label for spec in PROVIDERS.values()]
    selected_provider_label = st.selectbox(
        "Image provider",
        studio_provider_labels,
        index=list(PROVIDERS).index(studio_provider_id),
    )
    selected_provider_id = provider_id_from_label(selected_provider_label)
    if selected_provider_id != studio_provider_id:
        _set_active_provider(selected_provider_id)
        studio_provider_id = selected_provider_id
        settings = load_settings()

    studio_provider = get_provider(studio_provider_id)
    api_key, api_key_source = _provider_key(studio_provider_id)
    if api_key:
        st.success(f"Connected · {mask_key(api_key)}")
        st.caption(f"Source: {api_key_source}")
    else:
        st.warning(f"{studio_provider.label} is not connected.")

    connection_label = (
        "Change connection" if api_key else f"Connect {studio_provider.label}"
    )
    if st.button(
        connection_label,
        type="secondary" if api_key else "primary",
        width="stretch",
        key="studio_connect_provider",
    ):
        st.session_state.connect_return = "studio"
        st.session_state.connect_replace = bool(api_key)
        st.session_state.provider_choice = studio_provider_id
        st.session_state.connection_error = None
        st.session_state.screen = "connect"
        st.rerun()

    saved_model = _model_for(studio_provider_id, studio_provider, settings)
    model = st.selectbox(
        "Image model",
        list(studio_provider.models),
        index=list(studio_provider.models).index(saved_model),
    )
    quality = DEFAULT_QUALITY
    if studio_provider_id == "openai":
        saved_quality = str(settings.get("openai_quality", DEFAULT_QUALITY))
        if saved_quality not in {"low", "medium", "high"}:
            saved_quality = DEFAULT_QUALITY
        quality = st.select_slider(
            "Generation quality",
            options=["low", "medium", "high"],
            value=saved_quality,
        )

    if model != settings.get(f"{studio_provider_id}_model") or (
        studio_provider_id == "openai" and quality != settings.get("openai_quality")
    ):
        updated_settings = load_settings()
        updated_settings[f"{studio_provider_id}_model"] = model
        if studio_provider_id == "openai":
            updated_settings["openai_quality"] = quality
        save_settings(updated_settings)
        settings = updated_settings

    st.caption("Demo and upload modes work without a provider connection.")

    st.divider()
    st.markdown("### Print calibration")
    st.metric("Horizontal scale", f"{calibration_profile.x_scale * 100:.3f}%")
    st.metric("Vertical scale", f"{calibration_profile.y_scale * 100:.3f}%")
    if (
        abs(calibration_profile.x_offset_mm) > 0.001
        or abs(calibration_profile.y_offset_mm) > 0.001
    ):
        st.caption(
            f"Offset: x {calibration_profile.x_offset_mm:+.2f} mm, "
            f"y {calibration_profile.y_offset_mm:+.2f} mm"
        )

    st.divider()
    st.caption(f"Local data: {data_root()}")

create_tab, library_tab, calibration_tab, guide_tab = st.tabs(
    ["Create", "Saved doodles", "Print scale", "About"]
)

with create_tab:
    # Opening a saved doodle lands here, so the confirmation belongs here too.
    if st.session_state.library_notice:
        st.success(st.session_state.library_notice, icon=":material/check:")
        st.session_state.library_notice = ""

    st.markdown(
        '<div class="step-label">Step 1 · Choose the artwork source</div>',
        unsafe_allow_html=True,
    )
    source_mode = st.radio(
        "Artwork source",
        ["Generate with AI", "Upload artwork", "Use demo artwork"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if source_mode == "Generate with AI":
        with st.form("generation_form", clear_on_submit=False):
            idea = st.text_area(
                "Picture idea",
                key="generation_idea",
                height=90,
                help="Describe the subject and action. Captions are added later by the layout engine.",
            )
            field_1, field_2, field_3 = st.columns(3)
            with field_1:
                age_profile = st.selectbox("Who it is for", list(QUICK_AGE_CHOICES))
            with field_2:
                style_name = st.selectbox("Drawing profile", list(STYLE_PRESETS.keys()))
            with field_3:
                target = st.selectbox(
                    "Intended use", ["A4 page", "Round badge", "Flexible"]
                )

            field_4, field_5 = st.columns([1, 2])
            with field_4:
                variants = st.number_input(
                    "Alternatives", min_value=1, max_value=4, value=2, step=1
                )
            with field_5:
                extra = st.text_input(
                    "Extra direction",
                    placeholder="For example: wearing wellington boots",
                )

            generate_clicked = st.form_submit_button(
                "Draw it", type="primary", width="stretch", icon=":material/brush:"
            )

        if generate_clicked:
            if not idea.strip():
                st.error("Describe what Doodle should draw.")
            elif not api_key:
                st.session_state.generation_idea = idea.strip()
                st.session_state.connect_return = "studio"
                st.session_state.connect_replace = False
                st.session_state.provider_choice = studio_provider_id
                st.session_state.connection_error = None
                st.session_state.screen = "connect"
                st.rerun()
            elif _drawing_already_in_flight("busy_studio_generate"):
                # A queued replay of a click already being handled. Every
                # other paid control was guarded against this; this one sat
                # in top-level script code, not a function, and was left —
                # it spends money exactly as the others do.
                pass
            else:
                try:
                    with _mark_in_flight("busy_studio_generate"):
                        with st.spinner("Planning the alternatives…"):
                            briefs = build_variation_briefs(
                                idea,
                                int(variants),
                                provider_id=studio_provider_id,
                                api_key=api_key,
                            )
                        variant_prompts = [
                            build_colouring_prompt(
                                idea,
                                age_profile=age_profile,
                                style_name=style_name,
                                target=target,
                                extra_instructions=extra,
                                variation_brief=brief,
                            )
                            for brief in briefs
                        ]
                        size = (
                            studio_provider.portrait_size
                            if target == "A4 page"
                            else studio_provider.square_size
                        )
                        # Advance before deriving the seed. Recraft is the
                        # only provider given a seed, and holding it fixed
                        # returned the identical set of pictures every time
                        # the same idea was submitted twice, with no control
                        # to break the tie.
                        st.session_state.generation_nonce = (
                            int(st.session_state.get("generation_nonce", 0)) + 1
                        )
                        nonce = int(st.session_state.generation_nonce)
                        seed_source = f"{idea}|{style_name}|{target}|{nonce}"
                        random_seed = int(
                            hashlib.sha256(seed_source.encode("utf-8")).hexdigest()[:8],
                            16,
                        )
                        with st.spinner(f"Drawing {int(variants)} doodle(s)..."):
                            artworks = generate_with_provider(
                                provider_id=studio_provider_id,
                                api_key=api_key,
                                prompts=variant_prompts,
                                model=model,
                                size=size,
                                quality=quality,
                                random_seed=random_seed,
                            )
                        for artwork, brief in zip(artworks, briefs):
                            artwork.metadata["brief"] = brief
                        st.session_state.candidates = artworks
                        first = artworks[0]
                        _set_current_artwork(
                            first.image_bytes,
                            title=idea,
                            metadata={
                                "source": first.provider,
                                "concept": idea,
                                "prompt": first.prompt,
                                "model": first.model,
                                "generation": first.metadata,
                            },
                        )
                        _start_version_chain(first)
                        st.success(
                            "Your doodles are ready. Choose one, then prepare it for print."
                        )
                except GeneratorError as exc:
                    if exc.code in {
                        "missing_key",
                        "authentication",
                        "permission",
                        "billing",
                        "verification",
                    }:
                        st.session_state.connection_error = (
                            _provider_connection_message(exc)
                        )
                        st.session_state.connect_return = "studio"
                        st.session_state.connect_replace = exc.code in {
                            "authentication",
                            "permission",
                        }
                        st.session_state.provider_choice = studio_provider_id
                        st.session_state.screen = "connect"
                        st.rerun()
                    _show_guidance(exc.code, detail=str(exc))
                except ValueError as exc:
                    _show_guidance("missing_prompt", detail=str(exc))

        if st.session_state.candidates:
            st.subheader("Choose a doodle")
            gallery = st.columns(2)
            for index, candidate in enumerate(st.session_state.candidates):
                with gallery[index % 2]:
                    st.image(candidate.image_bytes, width="stretch")
                    if st.button(
                        "Use this doodle",
                        key=f"candidate_{index}",
                        width="stretch",
                    ):
                        concept = st.session_state.current_metadata.get(
                            "concept", "Generated colouring picture"
                        )
                        _set_current_artwork(
                            candidate.image_bytes,
                            title=concept,
                            metadata={
                                "source": candidate.provider,
                                "concept": concept,
                                "prompt": candidate.prompt,
                                "model": candidate.model,
                                "generation": candidate.metadata,
                            },
                        )
                        # Picking a different alternative abandons the previous
                        # chain rather than grafting onto it.
                        _start_version_chain(candidate)
                        st.rerun()
            if len(st.session_state.candidates) > 1:
                with st.expander("How the alternatives differ"):
                    for index, candidate in enumerate(
                        st.session_state.candidates, start=1
                    ):
                        st.markdown(f"**Alternative {index}**")
                        st.caption(candidate.metadata.get("brief", "—"))

            prompt_value = st.session_state.current_metadata.get("prompt")
            if prompt_value:
                with st.expander("Exact generation prompt"):
                    st.code(prompt_value, language="text")

    elif source_mode == "Upload artwork":
        uploaded = st.file_uploader(
            "Upload a picture",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=False,
            help="PNG, JPG or WebP.",
        )
        upload_title = st.text_input("Artwork title", value="My colouring picture")
        if uploaded and st.button("Use uploaded artwork", type="primary"):
            # A phone photo used as "artwork" carries the same GPS, camera
            # make and capture time the characters door already strips from
            # an identical file (SEC-03); the original filename can carry a
            # child's name too, so it is dropped rather than recorded.
            try:
                prepared = prepare_photo(
                    uploaded.getvalue(), max_edge=MAX_ARTWORK_EDGE_PX
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                _set_current_artwork(
                    prepared,
                    title=upload_title,
                    metadata={"source": "Upload"},
                )
                st.rerun()

    else:
        demos = list_demo_artwork()
        demo_name = st.selectbox("Demo picture", list(demos.keys()))
        left, right = st.columns([2, 1])
        with left:
            st.image(str(demos[demo_name]), width="stretch")
        with right:
            st.write(
                "Use an original built-in drawing to test the complete print workflow without an API key."
            )
            if st.button("Use demo artwork", type="primary", width="stretch"):
                _set_current_artwork(
                    demos[demo_name].read_bytes(),
                    title=demo_name,
                    metadata={"source": "Built-in demo", "demo": demo_name},
                )
                st.rerun()

    if st.session_state.current_raw:
        st.divider()
        st.markdown(
            '<div class="step-label">Step 2 · Prepare clean line art</div>',
            unsafe_allow_html=True,
        )
        st.subheader(st.session_state.current_title or "Selected artwork")

        controls_1, controls_2, controls_3 = st.columns(3)
        with controls_1:
            threshold = st.slider(
                "Black/white threshold",
                min_value=80,
                max_value=250,
                value=240,
                help="Higher values retain more faint grey marks as black.",
            )
            auto_invert = st.checkbox(
                "Correct a dark background automatically", value=True
            )
        with controls_2:
            thicken_pixels = st.slider(
                "Thicken lines", min_value=0, max_value=3, value=0
            )
            despeckle_label = st.selectbox(
                "Remove tiny specks", ["Off", "Light", "Strong"]
            )
            despeckle_size = {"Off": 0, "Light": 3, "Strong": 5}[despeckle_label]
        with controls_3:
            crop_whitespace = st.checkbox("Crop excess white space", value=True)
            padding_percent = st.slider("White padding after crop", 0.0, 20.0, 5.0, 0.5)

        processed = _cached_process(
            st.session_state.current_raw,
            threshold,
            auto_invert,
            crop_whitespace,
            padding_percent,
            despeckle_size,
            thicken_pixels,
        )
        processing_options = ProcessingOptions(
            threshold=threshold,
            auto_invert=auto_invert,
            crop_whitespace=crop_whitespace,
            padding_percent=padding_percent,
            despeckle_size=despeckle_size,
            thicken_pixels=thicken_pixels,
        )

        image_left, image_right = st.columns(2)
        with image_left:
            st.caption("Original")
            st.image(st.session_state.current_raw, width="stretch")
        with image_right:
            st.caption("Print-cleaned")
            st.image(processed, width="stretch")

        _render_refine_controls(key_prefix="studio")

        metrics = analyse_line_art(processed)
        metric_1, metric_2, metric_3 = st.columns(3)
        metric_1.metric("Processed width", f"{metrics['width_px']:,} px")
        metric_2.metric("Processed height", f"{metrics['height_px']:,} px")
        metric_3.metric("Black ink coverage", f"{metrics['ink_percent']:.2f}%")
        if metrics["ink_percent"] > 35:
            _show_guidance(
                "too_much_ink",
                detail=(
                    f"{metrics['ink_percent']:.1f}% of this picture is solid black."
                ),
            )
        elif metrics["ink_percent"] < 0.4:
            _show_guidance(
                "too_little_ink",
                detail=(
                    f"Only {metrics['ink_percent']:.2f}% of this picture is black line work."
                ),
            )

        png_col, save_col = st.columns([1, 1])
        with png_col:
            st.download_button(
                "Download cleaned PNG",
                data=processed,
                file_name=f"{_slug(st.session_state.current_title)}-clean.png",
                mime="image/png",
                width="stretch",
            )
        with save_col:
            save_title = st.text_input(
                "Name for this doodle",
                value=st.session_state.current_title or "Colouring picture",
                label_visibility="collapsed",
                placeholder="Name for this doodle",
            )
            if st.button(
                "Save to your doodles", width="stretch", icon=":material/favorite:"
            ):
                save_library_item(
                    processed_image=processed,
                    raw_image=st.session_state.current_raw,
                    title=save_title,
                    metadata={
                        **st.session_state.current_metadata,
                        "processing": asdict(processing_options),
                    },
                )
                st.success(
                    "Saved. You will find it under Saved doodles.",
                    icon=":material/check:",
                )

        st.divider()
        st.markdown(
            '<div class="step-label">Step 3 · Define the physical layout</div>',
            unsafe_allow_html=True,
        )
        layout_type = st.radio(
            "Output format",
            ["A4 colouring page", "A4 circle sheet", "Custom-size page"],
            horizontal=True,
        )

        pdf_config = None
        pdf_kind = ""
        summary = ""
        filename = "doodle.pdf"
        active_calibration = CalibrationProfile()
        current_pdf_signature = ""

        if layout_type == "A4 colouring page":
            c1, c2, c3 = st.columns(3)
            with c1:
                orientation = st.selectbox("Orientation", ["Portrait", "Landscape"])
            with c2:
                margin_mm = st.number_input("Margin (mm)", 5.0, 40.0, 12.0, 0.5)
            with c3:
                caption_size = st.number_input(
                    "Caption size (pt)", 7.0, 36.0, 17.0, 0.5
                )
            caption = st.text_input("Caption (optional)", value="")
            page_w, page_h = _orientation_dimensions(orientation)
            pdf_config = FullPageConfig(
                page_width_mm=page_w,
                page_height_mm=page_h,
                margin_mm=float(margin_mm),
                caption=caption,
                caption_font_size_pt=float(caption_size),
                caption_area_mm=27.0,
            )
            pdf_kind = "full"
            summary = f"A4 {orientation.lower()}: {page_w:g} x {page_h:g} mm"
            filename = f"{_slug(st.session_state.current_title)}-a4.pdf"

        elif layout_type == "A4 circle sheet":
            row_1 = st.columns(4)
            with row_1[0]:
                finished = st.number_input("Finished face (mm)", 10.0, 180.0, 58.0, 0.1)
            with row_1[1]:
                cut = st.number_input(
                    "Paper cut diameter (mm)",
                    10.0,
                    200.0,
                    58.0,
                    0.1,
                    help="Use the paper-template diameter specified by the badge press, which may exceed the finished face.",
                )
            with row_1[2]:
                safe = st.number_input(
                    "Safe artwork diameter (mm)", 5.0, 180.0, 50.0, 0.1
                )
            with row_1[3]:
                copies = st.number_input(
                    "Copies",
                    0,
                    100,
                    0,
                    1,
                    help="Leave at zero to fill the sheet with as many as fit.",
                )

            row_2 = st.columns(4)
            with row_2[0]:
                sheet_margin = st.number_input(
                    "Outer margin (mm)", 0.0, 40.0, 10.0, 0.5, key="circle_margin_mm"
                )
            with row_2[1]:
                gap = st.number_input("Gap between cuts (mm)", 0.0, 30.0, 5.0, 0.5)
            with row_2[2]:
                apply_calibration = st.checkbox("Apply saved calibration", value=False)
            with row_2[3]:
                circle_caption_size = st.number_input(
                    "Caption size (pt)", 5.0, 16.0, 7.5, 0.5
                )

            circle_caption = st.text_input("Caption (optional)", value="")
            guide_1, guide_2, guide_3 = st.columns(3)
            with guide_1:
                show_cut = st.checkbox("Show cut line", value=True)
            with guide_2:
                show_finished = st.checkbox("Show finished-face guide", value=False)
            with guide_3:
                show_safe = st.checkbox("Show safe-area guide", value=False)

            fit_choice = st.segmented_control(
                "Artwork fit",
                ["Fit the whole picture", "Fill the circle"],
                default="Fit the whole picture",
                help="Filling the circle draws the picture larger but cuts off its corners.",
            )

            pdf_config = CircleSheetConfig(
                finished_diameter_mm=float(finished),
                cut_diameter_mm=float(cut),
                safe_diameter_mm=float(safe),
                margin_mm=float(sheet_margin),
                gap_mm=float(gap),
                copies=int(copies),
                caption=circle_caption,
                caption_font_size_pt=float(circle_caption_size),
                show_cut_guide=show_cut,
                show_finished_guide=show_finished,
                show_safe_guide=show_safe,
                fit_mode="fill" if fit_choice == "Fill the circle" else "inscribe",
            )
            active_calibration = (
                calibration_profile if apply_calibration else CalibrationProfile()
            )
            try:
                plan = compute_circle_sheet_plan(pdf_config, active_calibration)
                st.markdown(
                    f'<div class="geometry-box"><strong>{plan.capacity}</strong> circles fit on the sheet '
                    f"({plan.columns} columns x {plan.rows} rows). "
                    f"This export will contain <strong>{len(plan.placements)}</strong>.</div>",
                    unsafe_allow_html=True,
                )
                summary = (
                    f"A4 circle sheet: finished {finished:g} mm; cut {cut:g} mm; "
                    f"safe {safe:g} mm; {len(plan.placements)} copies"
                )

                # A sheet that holds nothing is reported as a zero-capacity plan
                # rather than raised as an error, so it needs explaining here.
                if not plan.placements:
                    suggested = largest_margin_that_fits(pdf_config, active_calibration)
                    if suggested is None:
                        _show_guidance("badge_too_large")
                    else:
                        _show_guidance("no_circles_fit", suggested_margin_mm=suggested)
                        _offer_margin_fix(suggested)
                    summary = "No badges fit this sheet"

                badge_col, legend_col = st.columns([1, 1])
                with badge_col:
                    try:
                        st.image(
                            _cached_badge_preview(
                                processed,
                                json.dumps(asdict(pdf_config), sort_keys=True),
                                json.dumps(
                                    active_calibration.to_dict(), sort_keys=True
                                ),
                            ),
                            caption="One badge, actual proportions",
                            width="stretch",
                        )
                    except (ValueError, RuntimeError) as exc:
                        st.info(str(exc))
                with legend_col:
                    with st.container(border=True):
                        st.markdown("**Solid line** — where the paper is cut.")
                        st.markdown("**Dashed line** — the visible face once pressed.")
                        st.markdown(
                            "**Dotted line** — keep faces, eyes and text inside this."
                        )
                        if pdf_config.fit_mode == "inscribe":
                            st.caption(
                                "The whole picture is fitted inside the dotted circle, "
                                "so nothing is lost when the badge is made."
                            )
                        else:
                            st.caption(
                                "The picture fills the circle, so its four corners are "
                                "cut away. Switch to Fit the whole picture to keep them."
                            )
            except ValueError as exc:
                if "diameter" in str(exc).lower():
                    _show_guidance("invalid_circle_geometry", detail=str(exc))
                else:
                    suggested = largest_margin_that_fits(pdf_config, active_calibration)
                    if suggested is None:
                        _show_guidance("badge_too_large", detail=str(exc))
                    else:
                        _show_guidance(
                            "no_circles_fit",
                            detail=str(exc),
                            suggested_margin_mm=suggested,
                        )
                        _offer_margin_fix(suggested)
                summary = "Invalid circle layout"
            pdf_kind = "circle"
            filename = (
                f"{_slug(st.session_state.current_title)}-{finished:g}mm-circles.pdf"
            )

        else:
            custom_1, custom_2, custom_3 = st.columns(3)
            with custom_1:
                custom_w = st.number_input(
                    "PDF page width (mm)", 20.0, 500.0, 100.0, 0.1
                )
            with custom_2:
                custom_h = st.number_input(
                    "PDF page height (mm)", 20.0, 500.0, 100.0, 0.1
                )
            with custom_3:
                custom_margin = st.number_input("Margin (mm)", 0.0, 80.0, 5.0, 0.5)
            custom_caption = st.text_input("Caption (optional)", value="")
            custom_caption_size = st.number_input(
                "Caption size (pt)", 5.0, 30.0, 11.0, 0.5
            )
            pdf_config = CustomPageConfig(
                page_width_mm=float(custom_w),
                page_height_mm=float(custom_h),
                margin_mm=float(custom_margin),
                caption=custom_caption,
                caption_font_size_pt=float(custom_caption_size),
                caption_area_mm=16.0,
            )
            pdf_kind = "custom"
            summary = f"Custom PDF page: {custom_w:g} x {custom_h:g} mm"
            filename = f"{_slug(st.session_state.current_title)}-{custom_w:g}x{custom_h:g}mm.pdf"

        if pdf_config is not None and pdf_kind:
            current_pdf_signature = _build_signature(
                processed, pdf_kind, pdf_config, active_calibration
            )

        if st.button("Build print-ready PDF", type="primary", width="stretch"):
            try:
                if pdf_kind == "full":
                    pdf_bytes = create_full_page_pdf(processed, pdf_config)
                elif pdf_kind == "circle":
                    pdf_bytes, actual_count = create_circle_sheet_pdf(
                        processed, pdf_config, active_calibration
                    )
                    summary += f"; exported {actual_count}"
                elif pdf_kind == "custom":
                    pdf_bytes = create_custom_page_pdf(processed, pdf_config)
                else:
                    raise ValueError("Choose an output format.")
                st.session_state.pdf_bytes = pdf_bytes
                st.session_state.pdf_filename = filename
                st.session_state.pdf_summary = summary
                st.session_state.pdf_signature = current_pdf_signature
            except ValueError as exc:
                _show_guidance("pdf_failed", detail=str(exc))

        if (
            st.session_state.pdf_bytes
            and st.session_state.pdf_signature == current_pdf_signature
        ):
            st.subheader("Print preview")
            try:
                st.image(
                    _cached_preview(st.session_state.pdf_bytes),
                    width="stretch",
                )
            except RuntimeError as exc:
                st.info(str(exc))
            st.markdown(
                f'<div class="geometry-box"><strong>Geometry:</strong> '
                f"{st.session_state.pdf_summary}</div>",
                unsafe_allow_html=True,
            )
            if st.button(
                "Print this layout",
                type="primary",
                width="stretch",
                icon=":material/print:",
                key="print_studio",
            ):
                _send_to_printer(st.session_state.pdf_bytes)
            _render_print_help(
                st.session_state.pdf_bytes,
                file_name=st.session_state.pdf_filename,
                key="studio",
            )
        elif st.session_state.pdf_bytes:
            st.warning(
                "The artwork or layout settings have changed since this PDF was built. Build it again before printing."
            )

    else:
        st.info("Generate, upload or choose a demo picture to begin.")

with library_tab:
    st.header("Saved doodles")
    st.caption(f"Kept on this computer, in {data_root()}.")
    _render_library_grid()

with calibration_tab:
    st.header("Print scale")
    st.write(
        "PDF geometry is exact, but printer software may rescale it. This page measures that final physical distortion."
    )

    calibration_bytes = _calibration_pdf()
    preview_col, action_col = st.columns([2, 1])
    with preview_col:
        st.image(_cached_preview(calibration_bytes, dpi=95), width="stretch")
    with action_col:
        if st.button(
            "Print the calibration page",
            type="primary",
            width="stretch",
            icon=":material/print:",
            key="print_calibration",
        ):
            _send_to_printer(calibration_bytes)
        st.markdown(
            "1. Print at **Actual size / 100%**.\n\n"
            "2. Measure both 100 mm lines.\n\n"
            "3. Enter the measured lengths below."
        )
        _render_print_help(
            calibration_bytes,
            file_name="doodle-printer-calibration.pdf",
            key="calibration",
            scale_note=False,
        )

    measure_1, measure_2 = st.columns(2)
    with measure_1:
        measured_x = st.number_input(
            "Measured horizontal line (mm)", 50.0, 150.0, 100.0, 0.1
        )
        offset_x = st.number_input(
            "Optional horizontal offset (mm)",
            -20.0,
            20.0,
            calibration_profile.x_offset_mm,
            0.1,
        )
    with measure_2:
        measured_y = st.number_input(
            "Measured vertical line (mm)", 50.0, 150.0, 100.0, 0.1
        )
        offset_y = st.number_input(
            "Optional vertical offset (mm)",
            -20.0,
            20.0,
            calibration_profile.y_offset_mm,
            0.1,
        )

    proposed = profile_from_measurements(
        float(measured_x),
        float(measured_y),
        x_offset_mm=float(offset_x),
        y_offset_mm=float(offset_y),
    )
    result_1, result_2 = st.columns(2)
    result_1.metric(
        "Proposed horizontal compensation", f"{proposed.x_scale * 100:.3f}%"
    )
    result_2.metric("Proposed vertical compensation", f"{proposed.y_scale * 100:.3f}%")

    save_cal_col, reset_cal_col = st.columns(2)
    with save_cal_col:
        if st.button("Save calibration profile", type="primary", width="stretch"):
            updated = load_settings()
            updated["calibration"] = proposed.to_dict()
            save_settings(updated)
            st.rerun()
    with reset_cal_col:
        if st.button("Reset to 100%", width="stretch"):
            updated = load_settings()
            updated["calibration"] = CalibrationProfile().to_dict()
            save_settings(updated)
            st.rerun()

    st.caption(
        "Calibration is optional and is only applied when you tick Apply saved calibration on a circle sheet. "
        "Always test one sheet before a large batch."
    )

with guide_tab:
    st.header("How Doodle works")
    st.markdown(
        """
        **The AI controls the drawing; normal code controls the print geometry.** This distinction is what makes the output reusable.

        1. Generate an original picture, upload one, or use a built-in test drawing.
        2. Convert it to strict black and white, crop excess space and adjust line weight.
        3. Export it as an A4 page, an A4 sheet of exact circles, or a custom-size PDF page.
        4. Print at Actual size / 100%.

        For badges, keep three dimensions separate:

        - **Finished face:** the visible badge diameter, such as 58 mm.
        - **Paper cut:** the disc required by your badge press. It may be larger than the finished face because paper wraps around the shell.
        - **Safe artwork area:** the central zone in which eyes, faces and text must remain.

        The generated illustration itself is probabilistic. Reusing the same words may produce a different drawing. The PDF page size, circle diameters, margins and spacing are deterministic.
        """
    )
    st.markdown(
        "**Privacy and files**\n\n"
        "Doodle sends the written idea to the drawing service you have "
        "connected. When you add a character, their name, the photograph, "
        "and the two descriptions beside it — what makes them recognisable, "
        "and how they really look — are all sent so it can draw a "
        "caricature portrait; every later picture starring that character, "
        "and every badge composed from one, sends the same name, "
        "photograph and descriptions again, so the likeness always comes "
        "from the photograph rather than from the drawn portrait. A "
        "dropped connection can make the same request send again before it "
        "succeeds, photograph included — ordinary here, and nothing beyond "
        "that one request goes anywhere new. Both the photograph and the "
        "portrait stay on this computer, in the local data folder, along "
        "with your saved doodles.\n\n"
        "Removing a character deletes their photograph from this computer, "
        "which is the only copy Doodle has; it cannot recall anything a "
        "drawing service has already been sent. What each service does with "
        "what it receives is set out in its own terms, not here."
    )
