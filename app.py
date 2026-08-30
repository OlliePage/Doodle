from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict
from datetime import datetime

import streamlit as st

from colouring_factory.calibration import profile_from_measurements
from colouring_factory.demo import list_demo_artwork
from colouring_factory.generators import GeneratorError, generate_with_openai
from colouring_factory.version import build_label
from colouring_factory.image_processing import analyse_line_art, normalise_line_art
from colouring_factory.layouts import compute_circle_sheet_plan
from colouring_factory.models import (
    CalibrationProfile,
    CircleSheetConfig,
    CustomPageConfig,
    FullPageConfig,
    ProcessingOptions,
)
from colouring_factory.pdf_export import (
    create_calibration_pdf,
    create_circle_sheet_pdf,
    create_custom_page_pdf,
    create_full_page_pdf,
)
from colouring_factory.preview import render_pdf_preview
from colouring_factory.prompts import STYLE_PRESETS, build_colouring_prompt
from colouring_factory.storage import (
    data_root,
    delete_library_item,
    list_library_items,
    load_library_image,
    load_settings,
    save_library_item,
    save_settings,
)


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
      }

      #MainMenu, footer {visibility: hidden;}
      [data-testid="stDecoration"] {display: none;}
      .block-container,
      [data-testid="stMainBlockContainer"] {
        max-width: 1180px;
        padding-top: 1.25rem;
        padding-bottom: 3rem;
      }
      [data-testid="stSidebar"] .block-container {padding-top: 1.2rem;}
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
        margin: -.15rem 0 1.25rem;
      }
      .doodle-logo {
        position: relative;
        display: table;
        color: var(--doodle-ink);
        font-family: "Arial Rounded MT Bold", "Trebuchet MS", "Avenir Next", sans-serif;
        font-weight: 900;
        line-height: .92;
        letter-spacing: -.105em;
        white-space: nowrap;
        user-select: none;
      }
      .doodle-logo--hero {
        margin: 0 auto 2.25rem;
        font-size: clamp(4.9rem, 12vw, 8.15rem);
        padding-right: .16em;
      }
      .doodle-logo--compact {
        margin: .15rem 0 .4rem;
        font-size: 2.15rem;
        padding-right: .16em;
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
        top: -.24em;
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
        margin: .14em auto 0;
        border-top: .055em solid #202124;
        border-radius: 50%;
        transform: rotate(-1.5deg);
      }
      div[data-testid="stButton"] > button,
      div[data-testid="stDownloadButton"] > button {
        border-radius: 999px;
      }
      .stTabs [data-baseweb="tab-list"] {gap: .35rem;}
      .stTabs [data-baseweb="tab"] {border-radius: 999px; padding-left: 1rem; padding-right: 1rem;}
      .stTabs [aria-selected="true"] {background: var(--doodle-soft);}
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
      .doodle-build {{
        position: fixed;
        right: .75rem;
        bottom: .5rem;
        z-index: 1000;
        font-size: .7rem;
        font-variant-numeric: tabular-nums;
        color: var(--doodle-muted, #676b70);
        opacity: .7;
        pointer-events: none;
        user-select: none;
      }}
    </style>
    <div class="doodle-build">{build_label()}</div>
    """
)


def _doodle_logo(mode: str = "compact") -> str:
    return f"""
    <div class="doodle-logo doodle-logo--{mode}" aria-label="Doodle">
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
        "studio_open": False,
        "home_prompt": "",
        "generation_idea": "A cheerful baby dinosaur washing a toy fire engine",
        "candidates": [],
        "current_raw": None,
        "current_metadata": {},
        "current_title": "",
        "pdf_bytes": None,
        "pdf_filename": "doodle.pdf",
        "pdf_summary": "",
        "pdf_signature": "",
        "library_notice": "",
        "first_run": False,
        "result_mode": False,
        "quick_processed": None,
        "quick_pdf": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


_initialise_state()


def _open_studio_from_home() -> None:
    prompt = str(st.session_state.get("home_prompt", "")).strip()
    if not prompt:
        return
    st.session_state.generation_idea = prompt
    st.session_state.studio_open = True


def _start_new_doodle() -> None:
    st.session_state.studio_open = False
    st.session_state.home_prompt = ""
    st.session_state.generation_idea = ""
    st.session_state.candidates = []
    st.session_state.current_raw = None
    st.session_state.current_metadata = {}
    st.session_state.current_title = ""
    st.session_state.pdf_bytes = None
    st.session_state.pdf_summary = ""
    st.session_state.pdf_signature = ""
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
            min-height: 100vh;
            padding: 0 1.35rem 10vh !important;
            display: flex;
            flex-direction: column;
            justify-content: center;
          }
          div[data-testid="stTextInput"] {
            width: min(100%, 730px);
            margin: 0 auto;
          }
          div[data-testid="stTextInput"] > div > div,
          div[data-baseweb="input"] {
            min-height: 64px;
            border-radius: 999px !important;
            border-color: #dfe1e5 !important;
            background: #fff !important;
            box-shadow: 0 1px 6px rgba(32, 33, 36, .20);
            transition: box-shadow .16s ease, border-color .16s ease;
          }
          div[data-testid="stTextInput"] > div > div:hover,
          div[data-testid="stTextInput"] > div > div:focus-within,
          div[data-baseweb="input"]:hover,
          div[data-baseweb="input"]:focus-within {
            border-color: transparent !important;
            box-shadow: 0 2px 10px rgba(32, 33, 36, .24);
          }
          div[data-testid="stTextInput"] input {
            height: 62px;
            padding: 0 1.7rem;
            border-radius: 999px;
            font-size: 1.08rem;
            color: #202124;
            caret-color: #4f46e5;
          }
          div[data-testid="stTextInput"] input::placeholder {color: #858a91; opacity: 1;}
          @media (max-width: 640px) {
            .doodle-logo--hero {font-size: clamp(4.1rem, 22vw, 6rem); margin-bottom: 1.9rem;}
            div[data-testid="stTextInput"] > div > div,
            div[data-baseweb="input"] {min-height: 58px;}
            div[data-testid="stTextInput"] input {height: 56px; font-size: 1rem; padding: 0 1.3rem;}
          }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(_doodle_logo("hero"), unsafe_allow_html=True)
    st.text_input(
        "Describe a picture to colour",
        key="home_prompt",
        placeholder="What shall we draw?",
        label_visibility="collapsed",
        on_change=_open_studio_from_home,
    )


if st.session_state.current_raw is not None:
    st.session_state.studio_open = True

if not st.session_state.studio_open:
    _render_homepage()
    st.stop()


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


@st.cache_data(show_spinner=False)
def _calibration_pdf() -> bytes:
    return create_calibration_pdf()


def _set_current_artwork(raw: bytes, *, title: str, metadata: dict) -> None:
    st.session_state.studio_open = True
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


def _build_signature(image_bytes: bytes, kind: str, config: object, calibration: CalibrationProfile) -> str:
    payload = {
        "kind": kind,
        "config": asdict(config),
        "calibration": calibration.to_dict(),
    }
    digest = hashlib.sha256()
    digest.update(image_bytes)
    digest.update(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return digest.hexdigest()



def _quick_generate() -> None:
    idea = str(st.session_state.get("generation_idea", "")).strip()
    if not idea:
        return
    environment_key = os.getenv("OPENAI_API_KEY", "")
    api_key = str(st.session_state.get("quick_api_key", "") or environment_key)
    if not api_key:
        # Zero-friction prototype fallback: demonstrate the happy path without setup.
        demos = list_demo_artwork()
        raw = next(iter(demos.values())).read_bytes()
        _set_current_artwork(raw, title=idea, metadata={"source": "Built-in demo", "concept": idea})
        st.session_state.candidates = []
    else:
        prompt = build_colouring_prompt(
            idea,
            age_profile="2-3 years",
            style_name=list(STYLE_PRESETS.keys())[0],
            target="A4 page",
            extra_instructions="One clear subject or action, generous white space, no caption or text.",
        )
        artworks = generate_with_openai(api_key=api_key, prompt=prompt, variants=1, model="gpt-image-2", size="1024x1536", quality="medium")
        art = artworks[0]
        _set_current_artwork(art.image_bytes, title=idea, metadata={"source": art.provider, "concept": idea, "prompt": art.prompt, "model": art.model})
    processed = _cached_process(st.session_state.current_raw, 215, True, True, 5.0, 3, 0)
    config = FullPageConfig(page_width_mm=210.0, page_height_mm=297.0, margin_mm=12.0, caption="", caption_font_size_pt=17.0, caption_area_mm=27.0)
    st.session_state.quick_processed = processed
    st.session_state.quick_pdf = create_full_page_pdf(processed, config)
    st.session_state.result_mode = True


def _render_first_result() -> None:
    st.markdown("""
    <style>
      [data-testid="stSidebar"], [data-testid="collapsedControl"] {display:none !important;}
      .block-container,[data-testid="stMainBlockContainer"] {max-width:760px!important;padding-top:1rem!important;}
      .happy-title{text-align:center;font-size:1.05rem;color:#676b70;margin:.2rem 0 1rem;}
    </style>
    """, unsafe_allow_html=True)
    st.markdown(_doodle_logo("compact"), unsafe_allow_html=True)
    st.markdown('<div class="happy-title">Your first Doodle is ready.</div>', unsafe_allow_html=True)
    st.image(st.session_state.quick_processed, use_container_width=True)
    a,b,c=st.columns([1,1,1.25])
    with a:
        if st.button("↻ Again", use_container_width=True):
            st.session_state.result_mode=False
            try:
                with st.spinner("Drawing another one…"):
                    _quick_generate()
            except (ValueError, GeneratorError) as exc:
                st.error(str(exc))
            st.rerun()
    with b:
        if st.button("♡ Love it", use_container_width=True):
            save_library_item(processed_image=st.session_state.quick_processed, raw_image=st.session_state.current_raw, title=st.session_state.current_title or "Doodle", metadata=st.session_state.current_metadata)
            st.toast("Saved to your Doodles")
    with c:
        st.download_button("Print my Doodle", data=st.session_state.quick_pdf, file_name=f"{_slug(st.session_state.current_title)}-a4.pdf", mime="application/pdf", type="primary", use_container_width=True)
    change = st.text_input("Make a change", placeholder="Make the dinosaur wear a party hat…", label_visibility="collapsed")
    if change:
        st.session_state.generation_idea = f"{st.session_state.current_title}. Change it like this: {change}"
        st.session_state.result_mode=False
        try:
            with st.spinner("Making that change…"):
                _quick_generate()
        except (ValueError, GeneratorError) as exc:
            st.error(str(exc))
        st.rerun()
    with st.expander("Other sizes & advanced options"):
        st.caption("Need badges, custom millimetre dimensions, captions or printer calibration?")
        if st.button("Open Doodle Studio", use_container_width=True):
            st.session_state.first_run=False
            st.session_state.result_mode=False
            st.rerun()

settings = load_settings()
calibration_profile = CalibrationProfile.from_dict(settings.get("calibration"))

# First-run happy path: prompt -> one result -> print. Advanced controls remain available only on demand.
if st.session_state.get("first_run", True):
    if not st.session_state.get("result_mode", False):
        try:
            with st.spinner("Drawing your Doodle…"):
                _quick_generate()
        except (ValueError, GeneratorError) as exc:
            st.error(str(exc))
            st.text_input("OpenAI API key", key="quick_api_key", type="password", placeholder="Paste an API key to try again")
            if st.button("Try again", type="primary"):
                st.rerun()
            st.stop()
    _render_first_result()
    st.stop()

brand_col, new_col = st.columns([6, 1])
with brand_col:
    st.markdown(_doodle_logo("compact"), unsafe_allow_html=True)
    st.markdown(
        '<div class="studio-subtitle">Turn an idea into a print-ready colouring page.</div>',
        unsafe_allow_html=True,
    )
with new_col:
    if st.button("New doodle", use_container_width=True):
        _start_new_doodle()

with st.sidebar:
    st.markdown("### Settings")
    environment_key = os.getenv("OPENAI_API_KEY", "")
    api_key = st.text_input(
        "OpenAI API key",
        value=environment_key,
        type="password",
        help="Kept in this app session and never written to the artwork library.",
    )
    model = st.selectbox("Image model", ["gpt-image-2", "gpt-image-1.5", "gpt-image-1"], index=0)
    quality = st.select_slider("Generation quality", options=["low", "medium", "high"], value="medium")
    st.caption("Demo and upload modes work without an API key.")

    st.divider()
    st.markdown("### Print calibration")
    st.metric("Horizontal scale", f"{calibration_profile.x_scale * 100:.3f}%")
    st.metric("Vertical scale", f"{calibration_profile.y_scale * 100:.3f}%")
    if abs(calibration_profile.x_offset_mm) > 0.001 or abs(calibration_profile.y_offset_mm) > 0.001:
        st.caption(
            f"Offset: x {calibration_profile.x_offset_mm:+.2f} mm, "
            f"y {calibration_profile.y_offset_mm:+.2f} mm"
        )

    st.divider()
    st.caption(f"Local data: {data_root()}")

create_tab, library_tab, calibration_tab, guide_tab = st.tabs(
    ["Create", "Saved", "Print scale", "About"]
)

with create_tab:
    st.markdown('<div class="step-label">Step 1 - Choose the artwork source</div>', unsafe_allow_html=True)
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
                age_profile = st.selectbox("Child profile", ["2-3 years", "4-5 years"])
            with field_2:
                style_name = st.selectbox("Drawing profile", list(STYLE_PRESETS.keys()))
            with field_3:
                target = st.selectbox("Intended use", ["A4 page", "Round badge", "Flexible"])

            field_4, field_5 = st.columns([1, 2])
            with field_4:
                variants = st.number_input("Alternatives", min_value=1, max_value=4, value=2, step=1)
            with field_5:
                extra = st.text_input("Extra direction", placeholder="For example: wearing wellington boots")

            generate_clicked = st.form_submit_button("Create doodles", type="primary", use_container_width=True)

        if generate_clicked:
            try:
                generated_prompt = build_colouring_prompt(
                    idea,
                    age_profile=age_profile,
                    style_name=style_name,
                    target=target,
                    extra_instructions=extra,
                )
                size = "1024x1536" if target == "A4 page" else "1024x1024"
                with st.spinner(f"Drawing {int(variants)} doodle(s)..."):
                    artworks = generate_with_openai(
                        api_key=api_key,
                        prompt=generated_prompt,
                        variants=int(variants),
                        model=model,
                        size=size,
                        quality=quality,
                    )
                st.session_state.candidates = artworks
                first = artworks[0]
                _set_current_artwork(
                    first.image_bytes,
                    title=idea,
                    metadata={
                        "source": "OpenAI",
                        "concept": idea,
                        "prompt": first.prompt,
                        "model": first.model,
                        "generation": first.metadata,
                    },
                )
                st.success("Your doodles are ready. Choose one, then prepare it for print.")
            except (ValueError, GeneratorError) as exc:
                st.error(str(exc))

        if st.session_state.candidates:
            st.subheader("Choose a doodle")
            gallery = st.columns(2)
            for index, candidate in enumerate(st.session_state.candidates):
                with gallery[index % 2]:
                    st.image(candidate.image_bytes, use_container_width=True)
                    if st.button("Use this doodle", key=f"candidate_{index}", use_container_width=True):
                        concept = st.session_state.current_metadata.get("concept", "Generated colouring picture")
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
                        st.rerun()
            prompt_value = st.session_state.current_metadata.get("prompt")
            if prompt_value:
                with st.expander("Exact generation prompt"):
                    st.code(prompt_value, language="text")

    elif source_mode == "Upload artwork":
        uploaded = st.file_uploader(
            "Upload PNG, JPG or WebP artwork",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=False,
        )
        upload_title = st.text_input("Artwork title", value="My colouring picture")
        if uploaded and st.button("Use uploaded artwork", type="primary"):
            _set_current_artwork(
                uploaded.getvalue(),
                title=upload_title,
                metadata={"source": "Upload", "original_filename": uploaded.name},
            )
            st.rerun()

    else:
        demos = list_demo_artwork()
        demo_name = st.selectbox("Demo picture", list(demos.keys()))
        left, right = st.columns([2, 1])
        with left:
            st.image(str(demos[demo_name]), use_container_width=True)
        with right:
            st.write("Use an original built-in drawing to test the complete print workflow without an API key.")
            if st.button("Use demo artwork", type="primary", use_container_width=True):
                _set_current_artwork(
                    demos[demo_name].read_bytes(),
                    title=demo_name,
                    metadata={"source": "Built-in demo", "demo": demo_name},
                )
                st.rerun()

    if st.session_state.current_raw:
        st.divider()
        st.markdown('<div class="step-label">Step 2 - Prepare clean line art</div>', unsafe_allow_html=True)
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
            auto_invert = st.checkbox("Correct a dark background automatically", value=True)
        with controls_2:
            thicken_pixels = st.slider("Thicken lines", min_value=0, max_value=3, value=0)
            despeckle_label = st.selectbox("Remove tiny specks", ["Off", "Light", "Stronger"])
            despeckle_size = {"Off": 0, "Light": 3, "Stronger": 5}[despeckle_label]
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
            st.image(st.session_state.current_raw, use_container_width=True)
        with image_right:
            st.caption("Print-cleaned")
            st.image(processed, use_container_width=True)

        metrics = analyse_line_art(processed)
        metric_1, metric_2, metric_3 = st.columns(3)
        metric_1.metric("Processed width", f"{metrics['width_px']:,} px")
        metric_2.metric("Processed height", f"{metrics['height_px']:,} px")
        metric_3.metric("Black ink coverage", f"{metrics['ink_percent']:.2f}%")
        if metrics["ink_percent"] > 35:
            st.warning("This picture contains a large amount of solid black. Lower the threshold or choose a simpler source.")
        elif metrics["ink_percent"] < 0.4:
            st.warning("Very little line work remains. Raise the threshold.")

        png_col, save_col = st.columns([1, 1])
        with png_col:
            st.download_button(
                "Download cleaned PNG",
                data=processed,
                file_name=f"{_slug(st.session_state.current_title)}-clean.png",
                mime="image/png",
                use_container_width=True,
            )
        with save_col:
            save_title = st.text_input(
                "Library title",
                value=st.session_state.current_title or "Colouring picture",
                label_visibility="collapsed",
                placeholder="Library title",
            )
            if st.button("Save artwork to library", use_container_width=True):
                item_id = save_library_item(
                    processed_image=processed,
                    raw_image=st.session_state.current_raw,
                    title=save_title,
                    metadata={
                        **st.session_state.current_metadata,
                        "processing": asdict(processing_options),
                    },
                )
                st.session_state.library_notice = f"Saved as {item_id}."
                st.success("Saved to Doodle.")

        st.divider()
        st.markdown('<div class="step-label">Step 3 - Define the physical layout</div>', unsafe_allow_html=True)
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
                margin_mm = st.number_input("Page margin (mm)", 5.0, 40.0, 12.0, 0.5)
            with c3:
                caption_size = st.number_input("Caption size (pt)", 7.0, 36.0, 17.0, 0.5)
            caption = st.text_input("Optional caption", value="")
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
                safe = st.number_input("Safe artwork diameter (mm)", 5.0, 180.0, 50.0, 0.1)
            with row_1[3]:
                copies = st.number_input("Copies (0 = fill sheet)", 0, 100, 0, 1)

            row_2 = st.columns(4)
            with row_2[0]:
                sheet_margin = st.number_input("Outer margin (mm)", 0.0, 40.0, 10.0, 0.5)
            with row_2[1]:
                gap = st.number_input("Gap between cuts (mm)", 0.0, 30.0, 5.0, 0.5)
            with row_2[2]:
                apply_calibration = st.checkbox("Apply saved calibration", value=False)
            with row_2[3]:
                circle_caption_size = st.number_input("Badge caption size (pt)", 5.0, 16.0, 7.5, 0.5)

            circle_caption = st.text_input("Optional text inside every circle", value="")
            guide_1, guide_2, guide_3 = st.columns(3)
            with guide_1:
                show_cut = st.checkbox("Show cut line", value=True)
            with guide_2:
                show_finished = st.checkbox("Show finished-face guide", value=False)
            with guide_3:
                show_safe = st.checkbox("Show safe-area guide", value=False)

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
            )
            active_calibration = calibration_profile if apply_calibration else CalibrationProfile()
            try:
                plan = compute_circle_sheet_plan(pdf_config, active_calibration)
                st.markdown(
                    f'<div class="geometry-box"><strong>{plan.capacity}</strong> circles fit on the sheet '
                    f'({plan.columns} columns x {plan.rows} rows). '
                    f'This export will contain <strong>{len(plan.placements)}</strong>.</div>',
                    unsafe_allow_html=True,
                )
                summary = (
                    f"A4 circle sheet: finished {finished:g} mm; cut {cut:g} mm; "
                    f"safe {safe:g} mm; {len(plan.placements)} copies"
                )
            except ValueError as exc:
                st.error(str(exc))
                summary = "Invalid circle layout"
            pdf_kind = "circle"
            filename = f"{_slug(st.session_state.current_title)}-{finished:g}mm-circles.pdf"

        else:
            custom_1, custom_2, custom_3 = st.columns(3)
            with custom_1:
                custom_w = st.number_input("PDF page width (mm)", 20.0, 500.0, 100.0, 0.1)
            with custom_2:
                custom_h = st.number_input("PDF page height (mm)", 20.0, 500.0, 100.0, 0.1)
            with custom_3:
                custom_margin = st.number_input("Inner margin (mm)", 0.0, 80.0, 5.0, 0.5)
            custom_caption = st.text_input("Optional caption on custom page", value="")
            custom_caption_size = st.number_input("Custom caption size (pt)", 5.0, 30.0, 11.0, 0.5)
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
            current_pdf_signature = _build_signature(processed, pdf_kind, pdf_config, active_calibration)

        if st.button("Build print-ready PDF", type="primary", use_container_width=True):
            try:
                if pdf_kind == "full":
                    pdf_bytes = create_full_page_pdf(processed, pdf_config)
                elif pdf_kind == "circle":
                    pdf_bytes, actual_count = create_circle_sheet_pdf(processed, pdf_config, active_calibration)
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
                st.error(str(exc))

        if st.session_state.pdf_bytes and st.session_state.pdf_signature == current_pdf_signature:
            st.subheader("Print preview")
            try:
                st.image(_cached_preview(st.session_state.pdf_bytes), use_container_width=True)
            except RuntimeError as exc:
                st.info(str(exc))
            st.markdown(
                f'<div class="geometry-box"><strong>Geometry:</strong> '
                f'{st.session_state.pdf_summary}</div>',
                unsafe_allow_html=True,
            )
            st.download_button(
                "Download print-ready PDF",
                data=st.session_state.pdf_bytes,
                file_name=st.session_state.pdf_filename,
                mime="application/pdf",
                type="primary",
                use_container_width=True,
            )
            st.info("Print using Actual size or 100%. Disable Fit to page, Shrink and Scale to printable area.")
        elif st.session_state.pdf_bytes:
            st.warning("The artwork or layout settings have changed since this PDF was built. Build it again before printing.")

    else:
        st.info("Generate, upload or choose a demo picture to begin.")

with library_tab:
    st.header("Saved doodles")
    st.caption("Saved artwork stays on this computer.")
    if st.session_state.library_notice:
        st.success(st.session_state.library_notice)
        st.session_state.library_notice = ""

    library_items = list_library_items()
    if not library_items:
        st.info("The library is empty. Prepare a picture in Create, then save it.")
    else:
        library_columns = st.columns(3)
        for index, item in enumerate(library_items):
            with library_columns[index % 3]:
                with st.container(border=True):
                    st.image(item["processed_path"], use_container_width=True)
                    st.markdown(f"**{item.get('title', 'Untitled artwork')}**")
                    created = item.get("created_at", "")
                    try:
                        readable = datetime.fromisoformat(created).strftime("%d %b %Y, %H:%M")
                    except ValueError:
                        readable = created
                    st.caption(readable)
                    source = item.get("metadata", {}).get("source", "Unknown source")
                    st.caption(f"Source: {source}")
                    use_col, delete_col = st.columns(2)
                    with use_col:
                        if st.button("Use", key=f"load_{item['id']}", use_container_width=True):
                            artwork = load_library_image(item["id"], prefer_raw=False)
                            _set_current_artwork(
                                artwork,
                                title=item.get("title", "Library artwork"),
                                metadata={"source": "Library", "library_id": item["id"]},
                            )
                            st.success("Loaded. Open Create to lay it out.")
                    with delete_col:
                        if st.button("Delete", key=f"delete_{item['id']}", use_container_width=True):
                            delete_library_item(item["id"])
                            st.rerun()

with calibration_tab:
    st.header("Print scale")
    st.write(
        "PDF geometry is exact, but printer software may rescale it. This page measures that final physical distortion."
    )

    calibration_bytes = _calibration_pdf()
    preview_col, action_col = st.columns([2, 1])
    with preview_col:
        st.image(_cached_preview(calibration_bytes, dpi=95), use_container_width=True)
    with action_col:
        st.download_button(
            "Download calibration page",
            data=calibration_bytes,
            file_name="doodle-printer-calibration.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True,
        )
        st.markdown(
            "1. Print at **Actual size / 100%**.\n\n"
            "2. Measure both 100 mm lines.\n\n"
            "3. Enter the measured lengths below."
        )

    measure_1, measure_2 = st.columns(2)
    with measure_1:
        measured_x = st.number_input("Measured horizontal line (mm)", 50.0, 150.0, 100.0, 0.1)
        offset_x = st.number_input("Optional horizontal offset (mm)", -20.0, 20.0, calibration_profile.x_offset_mm, 0.1)
    with measure_2:
        measured_y = st.number_input("Measured vertical line (mm)", 50.0, 150.0, 100.0, 0.1)
        offset_y = st.number_input("Optional vertical offset (mm)", -20.0, 20.0, calibration_profile.y_offset_mm, 0.1)

    proposed = profile_from_measurements(
        float(measured_x),
        float(measured_y),
        x_offset_mm=float(offset_x),
        y_offset_mm=float(offset_y),
    )
    result_1, result_2 = st.columns(2)
    result_1.metric("Proposed horizontal compensation", f"{proposed.x_scale * 100:.3f}%")
    result_2.metric("Proposed vertical compensation", f"{proposed.y_scale * 100:.3f}%")

    save_cal_col, reset_cal_col = st.columns(2)
    with save_cal_col:
        if st.button("Save calibration profile", type="primary", use_container_width=True):
            updated = load_settings()
            updated["calibration"] = proposed.to_dict()
            save_settings(updated)
            st.rerun()
    with reset_cal_col:
        if st.button("Reset to 100%", use_container_width=True):
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
    st.subheader("Privacy and files")
    st.write(
        "AI mode sends the written prompt to the selected image provider. Uploaded pictures and saved doodles remain in the local data folder unless you separately send them elsewhere."
    )
