"""CivaMap — Streamlit UI on top of the existing Qdrant + Qwen backend."""

import math
import os
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.database import get_client, get_embedder, ensure_index, search_qdrant
from src.llm import answer, is_configured
from src.maps import directions_url, map_embed_url, map_search_url
from src.retrieval import load_resources

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
DATA_FILE = ROOT / "data" / "resource_directory.xlsx"
LOGO_FILE = ROOT / "assets" / "logo.png"

st.set_page_config(page_title="CivaMap · Find the support you need", page_icon="🧭", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
:root { --blue:#002169; --mid:#254893; --ink:#14233e; --muted:#67758a; --line:#e4eaf1; --pale:#f5f7fb; }
.stApp { background:#fbfcfe; color:var(--ink); }
[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stSidebar"], #MainMenu, footer { display:none !important; }
.block-container { max-width:1320px; padding-top:1.35rem !important; padding-bottom:4rem; }
h1,h2,h3 { color:var(--blue); letter-spacing:-.025em; }
h1 { font-size:2.6rem !important; }
h2 { font-size:1.55rem !important; }
[data-testid="stVerticalBlockBorderWrapper"] { border-color:var(--line) !important; }
[data-testid="stChatMessage"] { border:1px solid var(--line); background:#fff; border-radius:18px; }
[data-testid="stChatInput"] { border-radius:16px; }
.stButton > button, .stLinkButton > a, .stDownloadButton > button { border-radius:11px; min-height:2.55rem; font-weight:600; }
.stButton > button[kind="primary"], .stLinkButton > a[kind="primary"] { background:var(--blue) !important; color:#fff !important; border-color:var(--blue) !important; }
a { color:var(--mid); }
.brand { color:var(--blue); font-size:1.44rem; font-weight:800; letter-spacing:-.04em; margin:0; line-height:1.25; }
.brand-sub { color:var(--muted); font-size:.78rem; margin:0; }
.eyebrow { color:var(--mid); font-size:.74rem; font-weight:750; letter-spacing:.13em; text-transform:uppercase; }
.hero-title { font-size:clamp(2rem,3.4vw,3.3rem); line-height:1.13; font-weight:800; color:var(--blue); letter-spacing:-.045em; margin:.6rem 0; }
.hero-copy { font-size:1.05rem; line-height:1.65; color:#5f6e84; max-width:650px; }
.resource-name { color:var(--blue); font-weight:750; font-size:1.12rem; margin-bottom:.3rem; }
.resource-meta { color:var(--muted); font-size:.86rem; margin:.35rem 0; }
.resource-desc { color:#394b63; font-size:.94rem; line-height:1.55; margin:.65rem 0; }
.section-heading { font-size:1.55rem; color:var(--blue); font-weight:750; margin:0; }
.subtle { color:var(--muted); font-size:.92rem; }
.small-rule { height:1px; background:var(--line); margin:1rem 0 1.5rem; }
[data-baseweb="tab-list"] { gap:.55rem; }
[data-baseweb="tag"] { background:#eaf0fa !important; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def directory():
    return load_resources(DATA_FILE)


@st.cache_resource(show_spinner=False)
def services():
    return get_client(), get_embedder()


def value(row, key):
    raw = row.get(key, "")
    return "" if pd.isna(raw) else str(raw).strip()


def resource_id(row):
    return value(row, "Resource Name") + "|" + value(row, "Primary Service Area")


def shorten(txt, maximum=250):
    return txt if len(txt) <= maximum else txt[:maximum].rsplit(" ", 1)[0] + "…"


def fields_contain(row, *words):
    text = " ".join(value(row, field) for field in (
        "Eligibility and Cost", "Services Provided", "CHW Insider Tips", "Search Text (for semantic search)"
    )).lower()
    return any(word in text for word in words)


def verified_coords(row):
    """Coordinates are optional; don't approximate provider coordinates from service areas."""
    try:
        lat = float(value(row, "Latitude"))
        lon = float(value(row, "Longitude"))
        return (lat, lon) if -90 <= lat <= 90 and -180 <= lon <= 180 else None
    except (TypeError, ValueError):
        return None


def miles_between(a, b):
    radius = 3958.8
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    dlat, dlon = lat2-lat1, lon2-lon1
    h = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 2*radius*math.asin(min(1, math.sqrt(h)))


def filter_resources(rows, *, category="All categories", town="All towns / areas", cost="Any cost", access="Any accessibility", origin=None, radius=None, query=""):
    filtered = []
    for row in rows:
        if category != "All categories" and value(row, "Category") != category:
            continue
        if town != "All towns / areas" and town.lower() not in value(row, "Primary Service Area").lower():
            continue
        if query and query.lower() not in " ".join(value(row, k) for k in (
            "Resource Name", "Services Provided", "Category", "Primary Service Area", "Search Text (for semantic search)"
        )).lower():
            continue
        if cost == "Free (documented)" and not fields_contain(row, "free", "no cost", "no-cost"):
            continue
        if cost == "Low-cost / sliding scale (documented)" and not fields_contain(row, "low-cost", "low cost", "sliding scale", "reduced fee"):
            continue
        if access == "Accessibility mentioned" and not fields_contain(row, "wheelchair", "accessible", "accessibility", "ada compliant"):
            continue
        if radius is not None:
            coords = verified_coords(row)
            if origin is None or coords is None or miles_between(origin, coords) > radius:
                continue
        filtered.append(row)
    return filtered


def safe_url(url):
    return url if url.startswith(("https://", "http://")) else None


def contact_copy(row):
    return "\n".join(s for s in [
        value(row, "Resource Name"),
        value(row, "Phone / Contact"),
        value(row, "Website / Resource Link"),
        value(row, "Primary Service Area"),
    ] if s)


def resource_card(row, *, prefix):
    rid = resource_id(row)
    saved = rid in st.session_state.saved
    with st.container(border=True):
        st.markdown(f'<div class="resource-name">{html_escape(value(row,"Resource Name") or "Unnamed resource")}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="resource-meta">{html_escape(value(row,"Category"))} · {html_escape(value(row,"Primary Service Area") or "Service area unspecified")}</div>', unsafe_allow_html=True)
        description = value(row, "Services Provided") or value(row, "CHW Insider Tips")
        if description:
            st.markdown(f'<div class="resource-desc">{html_escape(shorten(description, 260))}</div>', unsafe_allow_html=True)
        with st.expander("Details, eligibility & contact"):
            for label, field in (("Eligibility / cost", "Eligibility and Cost"), ("Contact", "Phone / Contact"), ("Insider tips", "CHW Insider Tips"), ("Last checked", "Last Checked")):
                if value(row, field):
                    st.markdown(f"**{label}:** {value(row, field)}")
            site = safe_url(value(row, "Website / Resource Link"))
            if site:
                st.link_button("Provider website", site)
        a, b, c = st.columns(3)
        if a.button("Saved ✓" if saved else "♡ Save", key=f"save_{prefix}_{rid}", use_container_width=True):
            if saved:
                st.session_state.saved.remove(rid)
            else:
                st.session_state.saved.add(rid)
            st.rerun()
        if b.button("Copy contact", key=f"copy_{prefix}_{rid}", use_container_width=True):
            st.session_state.contact_open = rid if st.session_state.contact_open != rid else None
        if c.button("Share", key=f"share_{prefix}_{rid}", use_container_width=True):
            st.session_state.share_open = rid if st.session_state.share_open != rid else None
        if st.session_state.contact_open == rid:
            st.caption("Use the copy icon in the box below.")
            st.code(contact_copy(row), language=None)
        if st.session_state.share_open == rid:
            st.caption("Share the provider's website or a Google Maps search link:")
            link = safe_url(value(row, "Website / Resource Link")) or map_search_url(row)
            if link:
                st.code(link, language=None)
            else:
                st.code(contact_copy(row), language=None)
        if st.button("Report outdated information", key=f"report_{prefix}_{rid}"):
            st.session_state.report_target = rid
        if st.session_state.report_target == rid:
            with st.form(key=f"report_form_{prefix}_{rid}"):
                details = st.text_area("What information needs updating?", placeholder="e.g. This phone number is no longer in service.")
                submitted = st.form_submit_button("Prepare report")
            if submitted:
                if details.strip():
                    st.session_state.report_text = f"CivaMap listing report\nResource: {value(row, 'Resource Name')}\nArea: {value(row, 'Primary Service Area')}\nIssue: {details.strip()}\n"
                else:
                    st.warning("Please describe what needs updating.")
            if st.session_state.get("report_text"):
                st.download_button("Download report to send to directory maintainer", st.session_state.report_text,
                                   file_name="civamap_listing_report.txt", mime="text/plain", key=f"download_{prefix}_{rid}")
                st.caption("This prepares a report; it does not submit it automatically.")
        maps_link = map_search_url(row)
        if maps_link:
            st.link_button("View on Google Maps", maps_link, use_container_width=True)


def html_escape(text):
    from html import escape
    return escape(text)


def filters_ui(rows, key):
    categories = sorted({value(r, "Category") for r in rows if value(r, "Category")})
    areas = sorted({value(r, "Primary Service Area") for r in rows if value(r, "Primary Service Area")})
    with st.container(border=True):
        st.markdown("**Refine your search**")
        one, two, three = st.columns(3)
        category = one.selectbox("Category", ["All categories", *categories], key=f"cat_{key}")
        town = two.selectbox("Town / service area", ["All towns / areas", *areas], key=f"town_{key}")
        cost = three.selectbox("Cost", ["Any cost", "Free (documented)", "Low-cost / sliding scale (documented)"], key=f"cost_{key}")
        a, b = st.columns([1, 2])
        access = a.selectbox("Accessibility", ["Any accessibility", "Accessibility mentioned"], key=f"access_{key}")
        distance = b.selectbox("Distance", ["Any distance", "5 miles", "10 miles", "25 miles", "50 miles"], key=f"distance_{key}")
        origin = None
        radius = None
        if distance != "Any distance":
            st.caption("Distance uses coordinates, not service-area names. Only listings with verified Latitude and Longitude can be matched.")
            left, right = st.columns(2)
            lat = left.number_input("Your latitude", value=44.5646, format="%.5f", key=f"lat_{key}")
            lon = right.number_input("Your longitude", value=-69.6317, format="%.5f", key=f"lon_{key}")
            st.caption("Default coordinates are approximately downtown Waterville, not your current location. Edit them to use your location.")
            origin, radius = (lat, lon), float(distance.split()[0])
    return dict(category=category, town=town, cost=cost, access=access, origin=origin, radius=radius)


def map_panel(matches, selector_key="map"):
    possible = [(i, row) for i, row in enumerate(matches) if map_embed_url(row)]
    if not possible:
        st.info("No place-specific map searches for these results. Statewide and online services may not have a single destination.")
        return
    choices = dict(possible)
    idx = st.selectbox("Choose a resource to view", list(choices),
                       format_func=lambda i: value(choices[i], "Resource Name"), key=selector_key)
    row = choices[idx]
    st.components.v1.iframe(map_embed_url(row), height=390, scrolling=False)
    c1, c2 = st.columns(2)
    if map_search_url(row):
        c1.link_button("Open Google Maps", map_search_url(row), use_container_width=True)
    if directions_url(row):
        c2.link_button("Directions from my location", directions_url(row), type="primary", use_container_width=True)
    st.caption("Map searches are approximate: street addresses have not been verified. Google Maps may request your location for directions.")


try:
    resources = directory()
except Exception as exc:
    st.error(f"Unable to load the resource directory: {exc}")
    st.stop()

for key, default in {"messages": [], "saved": set(), "contact_open": None, "share_open": None,
                     "report_target": None, "report_text": "", "reindex": False}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# Header: logo and full-width primary navigation, with no sidebar.
brand, menu = st.columns([1, 3.5], vertical_alignment="center")
with brand:
    logo_col, name_col = st.columns([1, 3], vertical_alignment="center")
    with logo_col:
        if LOGO_FILE.is_file():
            st.image(str(LOGO_FILE), use_container_width=True)
        else:
            st.markdown("### ◉")
    with name_col:
        st.markdown('<p class="brand">CivaMap</p><p class="brand-sub">Community resource guide</p>', unsafe_allow_html=True)
with menu:
    page = st.segmented_control("Navigation", ["Home", "Browse Resources", "Map", "Saved Resources", "About"],
                                default="Home", key="nav", label_visibility="collapsed")
st.markdown('<div class="small-rule"></div>', unsafe_allow_html=True)

if page == "Home":
    intro, stat = st.columns([3, 1], vertical_alignment="center")
    with intro:
        st.markdown('<div class="eyebrow">LOCAL SUPPORT · CLEAR ANSWERS</div>', unsafe_allow_html=True)
        st.markdown('<div class="hero-title">Find the help you need.<br>All in one place.</div>', unsafe_allow_html=True)
        st.markdown('<div class="hero-copy">Ask CivaMap a question in everyday language. Explore real directory resources, save useful contacts, and get directions to local providers.</div>', unsafe_allow_html=True)
    with stat:
        with st.container(border=True):
            st.metric("Directory resources", len(resources))
            st.caption("Information should be confirmed with each provider before visiting.")
    st.write("")
    left, right = st.columns([1.12, 1], gap="large")
    with left:
        st.markdown('<div class="section-heading">Ask CivaMap</div>', unsafe_allow_html=True)
        st.caption("Powered by Qwen and retrieval from the CivaMap directory")
        if not is_configured():
            st.warning("Qwen is not configured. Check QWEN_BASE_URL and QWEN_MODEL in .env.")
        try:
            with st.spinner("Preparing resource search…"):
                client, embedder = services()
                ensure_index(client, embedder, resources, force=st.session_state.pop("reindex", False))
            ready = True
        except Exception as exc:
            st.error(f"Qdrant initialization failed: {exc}")
            ready = False
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg.get("sources"):
                    with st.expander(f"Sources ({len(msg['sources'])})"):
                        for r in msg["sources"]:
                            st.write("•", value(r, "Resource Name"))
        question = st.chat_input("Tell me what you need help with…", disabled=not (ready and is_configured()))
        if question:
            history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
            st.session_state.messages.append({"role": "user", "content": question})
            try:
                prior = [m["content"] for m in history if m["role"] == "user"][-2:]
                query = " ".join([*prior, question]) if len(question.split()) <= 7 else question
                with st.spinner("Finding relevant resources…"):
                    matches = search_qdrant(client, embedder, resources, query, limit=5)
                    response = answer(question, history, matches)
                st.session_state.messages.append({"role": "assistant", "content": response, "sources": matches})
            except Exception as exc:
                st.session_state.messages.append({"role": "assistant", "content": f"I couldn't complete that request. Please check your local Qwen/Qdrant setup. ({exc})"})
            st.rerun()
        if st.button("Start a new conversation"):
            st.session_state.messages = []
            st.rerun()
    with right:
        st.markdown('<div class="section-heading">Explore nearby resources</div>', unsafe_allow_html=True)
        st.caption("Recommended from your latest conversation")
        latest = next((m.get("sources", []) for m in reversed(st.session_state.messages) if m.get("sources")), [])
        if latest:
            map_panel(latest, "home_map_selection")
            with st.expander("Resources from this answer", expanded=True):
                for r in latest:
                    st.markdown(f"**{value(r, 'Resource Name')}** · {value(r, 'Primary Service Area')}")
        else:
            with st.container(border=True):
                st.markdown("**Your map will appear here.**")
                st.caption("Ask about food assistance, housing, transportation, healthcare, or another need to see matching providers.")

elif page == "Browse Resources":
    st.title("Browse resources")
    st.caption("Explore the directory and save resources you may want to revisit.")
    query = st.text_input("Search by keyword", placeholder="Food pantry, transportation, housing…")
    opts = filters_ui(resources, "browse")
    matches = filter_resources(resources, **opts, query=query)
    st.markdown(f"**{len(matches)} matching resources**")
    page_size = 12
    pages = max(1, math.ceil(len(matches)/page_size))
    number = st.number_input("Page", 1, pages, 1, key="browse_page")
    for i, row in enumerate(matches[(number-1)*page_size:number*page_size]):
        resource_card(row, prefix=f"browse_{number}_{i}")

elif page == "Map":
    st.title("Resource map")
    st.caption("Find a provider by service area, then view its Google Maps location search and directions.")
    opts = filters_ui(resources, "map")
    rows = filter_resources(resources, **opts)
    st.write(f"**{len(rows)} resources meet your filters**")
    map_panel(rows, "browse_map_selection")
    st.caption("This version displays one Google Maps search at a time because the directory doesn't yet contain verified coordinates for every provider.")

elif page == "Saved Resources":
    st.title("Saved resources")
    st.caption("Saved in this browser session only; clearing the session or restarting the app may remove them.")
    saved_rows = [r for r in resources if resource_id(r) in st.session_state.saved]
    if not saved_rows:
        st.info("You haven't saved any resources yet. Browse the directory and select ♡ Save.")
    for i, row in enumerate(saved_rows):
        resource_card(row, prefix=f"saved_{i}")

else:
    st.title("About CivaMap")
    st.markdown("""CivaMap is a prototype community resource assistant. It combines a curated resource directory with a locally run or institution-hosted language model and Qdrant retrieval.

**How it works:** Ask a question, review relevant resources, and confirm service details with the provider. The directory is not a substitute for official program eligibility guidance.

**Privacy:** A local Ollama/Qdrant setup can run on your computer. A hosted setup sends queries to the configured services. Maps links open Google Maps, subject to Google's privacy practices.

**Limitations:** Directory entries may be outdated. Town filters match the listed service area, not necessarily a provider's physical address. Free, low-cost and accessibility filters are based on wording in the directory and are not independently verified. Distance filtering works only for resources with verified latitude/longitude, using coordinates you provide. Reporting a listing creates a downloadable report; it does not automatically notify anyone.
""")
    with st.expander("Prototype status and maintenance"):
        st.write(f"Resources loaded: {len(resources)}")
        st.write("Qwen configured:", "Yes" if is_configured() else "No")
        st.write("Qdrant:", "Server" if os.getenv("QDRANT_URL") else "Local persistent storage")
        if st.button("Rebuild resource index"):
            st.session_state.reindex = True
            st.success("Index will rebuild next time you open Home.")
