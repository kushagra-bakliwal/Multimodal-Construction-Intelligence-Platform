"""
Multimodal Construction Intelligence Platform
SkillWallet Capstone - Project 1

Run locally:   streamlit run app.py
Deploy:        push app.py + requirements.txt to GitHub -> Streamlit Community Cloud
"""

import hashlib
import json
import re
import urllib.parse
from typing import Any, Dict, List, Optional

import requests
import streamlit as st
from PIL import Image, UnidentifiedImageError

# The new Google GenAI SDK is optional at import time so the app still runs in demo mode.
try:
    from google import genai
    from google.genai import types as genai_types

    GENAI_AVAILABLE = True
except Exception:  # pragma: no cover
    genai = None
    genai_types = None
    GENAI_AVAILABLE = False

# -----------------------------------------------------------------------------
# 0. CONFIGURATION
# -----------------------------------------------------------------------------
MODEL_NAME = "gemini-2.5-flash"
MAX_IMAGE_MB = 8
MAX_IMAGE_SIDE = 1600  # downscale big photos before sending to the API

st.set_page_config(
    page_title="Multimodal Construction Intelligence Platform",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
    .main-title { font-size: 2.2rem; font-weight: 700; color: inherit; margin-bottom: 0.2rem; }
    .sub-title  { font-size: 1.0rem; color: #64748B; margin-bottom: 1.5rem; }
    .pill { padding: 4px 14px; border-radius: 14px; font-weight: 600; display: inline-block; }
    .pill-green  { background: #DCFCE7; color: #166534; }
    .pill-amber  { background: #FEF3C7; color: #92400E; }
    .pill-red    { background: #FEE2E2; color: #991B1B; }
    .demo-banner { background: #EFF6FF; border: 1px solid #BFDBFE; color: #1E40AF;
                   padding: 8px 12px; border-radius: 8px; font-size: 0.9rem; margin-bottom: 0.8rem; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 1. DEMO-MODE FALLBACK DATA (varies per image so demo mode is not identical)
# -----------------------------------------------------------------------------
PPE_DEMO_SCENARIOS: List[Dict[str, Any]] = [
    {
        "safety_score": 68,
        "overall_status": "WARNING",
        "ppe_detection": {"helmets": True, "high_vis_vests": True, "steel_toe_boots": False, "safety_harnesses": False},
        "hazards": [
            {"hazard": "Worker near slab edge without a fall-arrest harness", "severity": "Critical",
             "remedy": "Enforce immediate tie-off with dual-leg shock-absorbing lanyards (OSHA 1926.501)."},
            {"hazard": "Scaffold platform missing guardrails and toe-boards", "severity": "High",
             "remedy": "Install top-rails (42 in) and mid-rails before work resumes."},
        ],
    },
    {
        "safety_score": 91,
        "overall_status": "COMPLIANT",
        "ppe_detection": {"helmets": True, "high_vis_vests": True, "steel_toe_boots": True, "safety_harnesses": True},
        "hazards": [
            {"hazard": "Loose rebar offcuts left on walkway", "severity": "Low",
             "remedy": "Introduce end-of-shift housekeeping sweep and designated scrap bins."},
        ],
    },
    {
        "safety_score": 42,
        "overall_status": "NON-COMPLIANT",
        "ppe_detection": {"helmets": False, "high_vis_vests": True, "steel_toe_boots": False, "safety_harnesses": False},
        "hazards": [
            {"hazard": "Multiple workers without hard hats under active overhead work", "severity": "Critical",
             "remedy": "Stop work in the zone; issue helmets and set up a barricaded drop zone."},
            {"hazard": "Exposed electrical cable across a wet working area", "severity": "High",
             "remedy": "Elevate or conduit all cables and fit RCD/GFCI protection."},
            {"hazard": "Unprotected excavation edge", "severity": "High",
             "remedy": "Install edge barricades with warning signage and a 1 m clear setback."},
        ],
    },
]

CRACK_DEMO_SCENARIOS: List[Dict[str, Any]] = [
    {
        "defect_type": "Structural Shear", "estimated_crack_width_mm": 3.4, "severity": "High",
        "severity_score": 78,
        "root_cause": "Differential foundation settlement with diagonal tension at load-bearing beam joints.",
        "recommended_repair": "Epoxy resin injection followed by structural re-grouting and CFRP wrap strengthening.",
        "urgency": "Immediate",
    },
    {
        "defect_type": "Hairline", "estimated_crack_width_mm": 0.2, "severity": "Low",
        "severity_score": 14,
        "root_cause": "Plastic/drying shrinkage from inadequate early-age curing.",
        "recommended_repair": "Surface sealing with polymer-modified cementitious slurry; improve curing practice.",
        "urgency": "Monitor Monthly",
    },
    {
        "defect_type": "Spalling", "estimated_crack_width_mm": 1.8, "severity": "Medium",
        "severity_score": 55,
        "root_cause": "Reinforcement corrosion from chloride/moisture ingress causing cover delamination.",
        "recommended_repair": "Remove loose concrete, treat rebar with anti-corrosive primer, apply repair mortar and re-grout.",
        "urgency": "Within 7 Days",
    },
]

CHAT_KB: Dict[str, str] = {
    "curing": "Per IS 456, moist-cure OPC concrete for at least 7 days (10 days where mineral admixtures or in hot/dry weather, and 10 days for blended cements).",
    "cover": "IS 456 minimum nominal cover: 20 mm mild, 30 mm moderate, 45 mm severe, 50 mm very severe and extreme exposure (for beams/slabs; columns have a 40 mm minimum for larger sections).",
    "mix": "Common nominal mixes: M15 (1:2:4), M20 (1:1.5:3), M25 (1:1:2). Use design mixes for M25 and above.",
    "slump": "Typical slump: 25-75 mm for footings/beams with vibration, 75-100 mm for slabs and columns, higher only with admixtures.",
    "helmet": "Hard hats are mandatory on any active construction zone; replace them after impact or per the manufacturer's shelf life (typically 2-5 years).",
    "harness": "Fall protection is required above 1.8 m (OSHA 1926.501 uses 6 ft). Use full-body harnesses with a certified anchor point.",
    "scaffold": "Scaffolds need base plates, bracing, complete platforms, guardrails and toe-boards, and a competent-person inspection before each shift.",
    "monsoon": "In monsoon: protect cement from moisture, check excavation slopes, pump out water, cover fresh concrete and suspend outdoor electrical work.",
    "steel": "Rule of thumb for residential RCC: 3-4 kg of steel per sq ft of built-up area; always verify against structural drawings.",
    "cement": "A rough estimate is 0.4 bags of cement per sq ft of built-up area for typical RCC framed construction.",
}
CHAT_DEFAULT = (
    "I can help with IS 456 concrete practice, site safety (OSHA), curing, scaffolding, "
    "material estimates and weather protocols. Add a Gemini API key in the sidebar for "
    "full, detailed answers to any construction question."
)

SYSTEM_INSTRUCTION = (
    "You are a senior construction site engineer and safety officer in India. Answer only questions about "
    "construction, civil engineering, site safety, materials, cost estimation, scheduling and building codes "
    "(IS 456, IS 800, NBC, OSHA). Be concise and practical, and cite the relevant standard where possible. "
    "If asked about unrelated topics, politely redirect to construction topics."
)

# -----------------------------------------------------------------------------
# 2. UTILITIES
# -----------------------------------------------------------------------------
def fmt_inr(amount: float) -> str:
    """Format a rupee amount as Crores (>= 1 Cr) or Lakhs."""
    if amount >= 1e7:
        return f"₹ {amount / 1e7:,.2f} Cr"
    return f"₹ {amount / 1e5:,.2f} Lakhs"


def load_image(uploaded_file) -> Optional[Image.Image]:
    """Safely open and normalise an uploaded image. Returns None on failure."""
    try:
        if uploaded_file.size > MAX_IMAGE_MB * 1024 * 1024:
            st.error(f"Image is larger than {MAX_IMAGE_MB} MB. Please upload a smaller file.")
            return None
        img = Image.open(uploaded_file)
        img.load()
        img = img.convert("RGB")
        if max(img.size) > MAX_IMAGE_SIDE:
            img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
        return img
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        st.error(f"Could not read that image ({exc}). Please upload a valid JPG or PNG.")
        return None


def image_fingerprint(img: Image.Image) -> int:
    return int(hashlib.md5(img.tobytes()[:200000]).hexdigest(), 16)


def pick_scenario(img: Image.Image, scenarios: List[Dict[str, Any]]) -> Dict[str, Any]:
    return json.loads(json.dumps(scenarios[image_fingerprint(img) % len(scenarios)]))


def extract_json(text: str) -> Dict[str, Any]:
    """Pull a JSON object out of a model response, tolerating code fences and extra prose."""
    text = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def get_client(api_key: str):
    if not (GENAI_AVAILABLE and api_key):
        return None
    return genai.Client(api_key=api_key)


# --- Schema validation / normalisation (prevents KeyErrors on bad model output) ---
SEVERITIES = ["Low", "Medium", "High", "Critical"]
STATUSES = ["COMPLIANT", "WARNING", "NON-COMPLIANT"]
DEFECTS = ["Hairline", "Settlement", "Structural Shear", "Thermal Expansion", "Spalling"]
URGENCIES = ["Immediate", "Within 7 Days", "Monitor Monthly"]


def _num(value: Any, default: float, lo: float, hi: float) -> float:
    try:
        return max(lo, min(hi, float(value)))
    except (TypeError, ValueError):
        return default


def _choice(value: Any, options: List[str], default: str) -> str:
    if isinstance(value, str):
        for opt in options:
            if value.strip().lower() == opt.lower():
                return opt
    return default


def normalize_ppe(data: Dict[str, Any]) -> Dict[str, Any]:
    ppe = data.get("ppe_detection") or {}
    hazards = []
    for h in data.get("hazards") or []:
        if isinstance(h, dict):
            hazards.append({
                "hazard": str(h.get("hazard", "Unspecified hazard")),
                "severity": _choice(h.get("severity"), SEVERITIES, "Medium"),
                "remedy": str(h.get("remedy", "Consult the site safety officer.")),
            })
    return {
        "safety_score": int(_num(data.get("safety_score"), 0, 0, 100)),
        "overall_status": _choice(data.get("overall_status"), STATUSES, "WARNING"),
        "ppe_detection": {
            "helmets": bool(ppe.get("helmets", False)),
            "high_vis_vests": bool(ppe.get("high_vis_vests", False)),
            "steel_toe_boots": bool(ppe.get("steel_toe_boots", False)),
            "safety_harnesses": bool(ppe.get("safety_harnesses", False)),
        },
        "hazards": hazards,
    }


def normalize_crack(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "defect_type": _choice(data.get("defect_type"), DEFECTS, "Hairline"),
        "estimated_crack_width_mm": round(_num(data.get("estimated_crack_width_mm"), 0.0, 0, 100), 2),
        "severity": _choice(data.get("severity"), SEVERITIES, "Medium"),
        "severity_score": int(_num(data.get("severity_score"), 50, 0, 100)),
        "root_cause": str(data.get("root_cause", "Not determined.")),
        "recommended_repair": str(data.get("recommended_repair", "Consult a structural engineer.")),
        "urgency": _choice(data.get("urgency"), URGENCIES, "Within 7 Days"),
    }


def analyze_image(api_key: str, image: Image.Image, prompt: str, demo_data: Dict[str, Any]) -> Dict[str, Any]:
    """Run multimodal analysis with Gemini, or return demo data. Never raises."""
    client = get_client(api_key)
    if client is None:
        if api_key and not GENAI_AVAILABLE:
            st.warning("The google-genai package is not installed. Running in demo mode.")
        return demo_data
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[prompt, image],
            config=genai_types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2),
        )
        return extract_json(response.text)
    except Exception as exc:
        st.warning(f"Live AI analysis failed ({type(exc).__name__}: {exc}). Showing demo inspection data instead.")
        return demo_data


def chat_fallback(question: str) -> str:
    q = question.lower()
    for key, answer in CHAT_KB.items():
        if key in q:
            return answer
    return CHAT_DEFAULT


def chat_reply(api_key: str, history: List[Dict[str, str]]) -> str:
    question = history[-1]["content"]
    client = get_client(api_key)
    if client is None:
        return chat_fallback(question)
    try:
        contents = [
            genai_types.Content(
                role="user" if m["role"] == "user" else "model",
                parts=[genai_types.Part(text=m["content"])],
            )
            for m in history[-12:]
        ]
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=genai_types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION, temperature=0.4),
        )
        return response.text or chat_fallback(question)
    except Exception as exc:
        return f"⚠️ Live AI is unavailable ({type(exc).__name__}). Offline answer:\n\n{chat_fallback(question)}"


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_render(url: str) -> Optional[bytes]:
    """Download the generated render with a timeout. Returns None on failure."""
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        if "image" not in resp.headers.get("Content-Type", ""):
            return None
        return resp.content
    except requests.RequestException:
        return None


# -----------------------------------------------------------------------------
# 3. PROMPTS
# -----------------------------------------------------------------------------
PPE_PROMPT = """You are a certified OSHA and IS 456 Construction Safety Inspector.
Analyze the construction site image and return ONLY a valid JSON object with exactly this schema:
{
  "safety_score": <integer 0-100>,
  "overall_status": "<COMPLIANT | WARNING | NON-COMPLIANT>",
  "ppe_detection": {"helmets": <boolean>, "high_vis_vests": <boolean>, "steel_toe_boots": <boolean>, "safety_harnesses": <boolean>},
  "hazards": [{"hazard": "<description>", "severity": "<Low | Medium | High | Critical>", "remedy": "<corrective action>"}]
}
Only mark PPE as true if clearly visible on the workers. If no workers are visible, mark all PPE false and mention it as a hazard.
"""

CRACK_PROMPT = """You are a structural engineer. Analyze the concrete/masonry surface image for defects and
return ONLY a valid JSON object with exactly this schema:
{
  "defect_type": "<Hairline | Settlement | Structural Shear | Thermal Expansion | Spalling>",
  "estimated_crack_width_mm": <number>,
  "severity": "<Low | Medium | High | Critical>",
  "severity_score": <integer 0-100, where 100 is most severe>,
  "root_cause": "<detailed cause>",
  "recommended_repair": "<engineering intervention, e.g. epoxy injection, structural re-grouting, CFRP wrapping>",
  "urgency": "<Immediate | Within 7 Days | Monitor Monthly>"
}
"""

# -----------------------------------------------------------------------------
# 4. PAGES
# -----------------------------------------------------------------------------
def pill_class(status: str) -> str:
    return {"COMPLIANT": "pill-green", "WARNING": "pill-amber"}.get(status, "pill-red")


def severity_color_fn(severity: str):
    return {"Low": st.info, "Medium": st.warning, "High": st.warning, "Critical": st.error}.get(severity, st.warning)


def render_ppe_page(api_key: str) -> None:
    st.header("Site Safety & Worker PPE Compliance Audit")
    st.caption("OSHA and IS 456 automated multimodal vision audit")

    col1, col2 = st.columns(2)
    with col1:
        upload = st.file_uploader("Upload Construction Site Image", type=["jpg", "jpeg", "png"], key="ppe_up")
        image = load_image(upload) if upload else None
        if image:
            st.image(image, caption="Uploaded Site Photo", width="stretch")
        else:
            st.info("👆 Upload a construction site photo to start the PPE inspection.")

    with col2:
        if image and st.button("Run Safety & PPE Audit", type="primary", width="stretch"):
            demo = pick_scenario(image, PPE_DEMO_SCENARIOS)
            with st.spinner("Analyzing image against safety compliance standards..."):
                raw = analyze_image(api_key, image, PPE_PROMPT, demo)
            st.session_state["ppe_result"] = normalize_ppe(raw)

        results = st.session_state.get("ppe_result")
        if image and results:
            m1, m2 = st.columns(2)
            m1.metric("Overall Safety Score", f"{results['safety_score']}/100")
            m2.markdown(
                f"**Compliance Status:** <span class='pill {pill_class(results['overall_status'])}'>"
                f"{results['overall_status']}</span>",
                unsafe_allow_html=True,
            )
            st.progress(results["safety_score"] / 100)

    results = st.session_state.get("ppe_result")
    if image and results:
        st.subheader("PPE Checklist Audit")
        ppe = results["ppe_detection"]
        labels = [("Hard Hats / Helmets", "helmets"), ("High-Vis Vests", "high_vis_vests"),
                  ("Steel-Toe Boots", "steel_toe_boots"), ("Safety Harnesses", "safety_harnesses")]
        cols = st.columns(4)
        for col, (label, key) in zip(cols, labels):
            col.metric(label, "✅ Detected" if ppe[key] else "❌ Missing")

        st.subheader("Identified Hazards & Corrective Actions")
        if not results["hazards"]:
            st.success("No hazards identified.")
        for hz in results["hazards"]:
            severity_color_fn(hz["severity"])(
                f"**[{hz['severity']} Severity]** {hz['hazard']}\n\n👉 **Corrective Action:** {hz['remedy']}"
            )

        st.download_button(
            "📥 Download JSON Safety Audit Report",
            data=json.dumps(results, indent=2),
            file_name="site_safety_audit_report.json",
            mime="application/json",
        )


def render_crack_page(api_key: str) -> None:
    st.header("Structural Crack Diagnostics & Integrity Assessment")
    st.caption("AI-assisted defect classification and remediation workflow")

    col1, col2 = st.columns(2)
    with col1:
        upload = st.file_uploader("Upload Structural / Wall Surface Photo", type=["jpg", "jpeg", "png"], key="crack_up")
        image = load_image(upload) if upload else None
        if image:
            st.image(image, caption="Concrete Surface Image", width="stretch")
        else:
            st.info("👆 Upload a concrete or masonry surface photo to evaluate structural integrity.")

    with col2:
        if image and st.button("Analyze Defect & Structural Risks", type="primary", width="stretch"):
            demo = pick_scenario(image, CRACK_DEMO_SCENARIOS)
            with st.spinner("Evaluating defect mechanics and severity..."):
                raw = analyze_image(api_key, image, CRACK_PROMPT, demo)
            st.session_state["crack_result"] = normalize_crack(raw)

        res = st.session_state.get("crack_result")
        if image and res:
            st.subheader("Diagnostic Results")
            st.error(f"**Defect Classification:** {res['defect_type']}")
            c1, c2 = st.columns(2)
            c1.metric("Estimated Width", f"{res['estimated_crack_width_mm']} mm")
            c2.metric("Action Urgency", res["urgency"])
            c3, c4 = st.columns(2)
            c3.metric("Severity Level", res["severity"])
            c4.metric("Severity Score", f"{res['severity_score']}/100")
            st.progress(res["severity_score"] / 100)

    res = st.session_state.get("crack_result")
    if image and res:
        st.markdown(f"**Root Cause Analysis:**\n\n{res['root_cause']}")
        st.markdown(f"**Recommended Repair Protocol:**\n\n{res['recommended_repair']}")
        st.download_button(
            "📥 Download JSON Crack Report",
            data=json.dumps(res, indent=2),
            file_name="crack_diagnostics_report.json",
            mime="application/json",
        )


def render_planning_page() -> None:
    st.header("Project Planning, Valuation & Materials Estimator")
    st.caption("Indian market real estate valuation engine (INR) and 3D concept visualisation")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Project Parameters")
        struct_type = st.selectbox(
            "Structure Type",
            ["Residential Apartment", "Commercial Complex", "Industrial Warehouse", "Villa / Gated Community"],
        )
        built_up = st.number_input("Built-up Area (Sq. Ft.)", min_value=500, max_value=1_000_000, value=5500, step=500)
        tier = st.selectbox(
            "Location Tier (Indian Cities)",
            ["Tier 1 (Mumbai, Delhi NCR, Bengaluru)", "Tier 2 (Pune, Ahmedabad, Jaipur)", "Tier 3 / Regional"],
        )
        completion = st.slider("Completion Percentage (%)", 0, 100, 45)

    # --- calculations (INR) ---
    base_rate = 2400 if "Tier 1" in tier else (1800 if "Tier 2" in tier else 1400)
    multipliers = {"Commercial Complex": 1.3, "Industrial Warehouse": 0.9, "Villa / Gated Community": 1.2}
    base_rate *= multipliers.get(struct_type, 1.0)

    total_budget = built_up * base_rate
    capex = total_budget * completion / 100
    market_value = total_budget * 1.35  # developer margin / market premium
    steel_tons = built_up * 3.5 / 1000  # ~3.5 kg per sq ft
    cement_bags = built_up * 0.4  # ~0.4 bags per sq ft

    with col2:
        st.subheader("Financial & Material Valuation Metrics")
        f1, f2 = st.columns(2)
        f1.metric("Est. Total Budget", fmt_inr(total_budget))
        f2.metric("Market Asset Value", fmt_inr(market_value))
        f3, f4 = st.columns(2)
        f3.metric("Capex Incurred", fmt_inr(capex))
        f4.metric("Balance to Spend", fmt_inr(total_budget - capex))
        st.caption(f"Milestone progress: {completion}% complete")
        st.progress(completion / 100)

        st.divider()
        st.subheader("Core Material Requirements")
        m1, m2 = st.columns(2)
        m1.metric("Structural Steel Required", f"{steel_tons:,.1f} Tons")
        m2.metric("Cement Required", f"{int(cement_bags):,} Bags")
        st.caption(f"Assumed construction rate: ₹ {base_rate:,.0f} per sq ft. Indicative estimate only.")

    st.divider()
    st.subheader("Conceptual 3D Architectural Rendering")
    prompt_text = (
        f"Modern architectural 3D render of a {struct_type}, {built_up} sqft, "
        f"{completion}% complete construction site, exterior view, photorealistic"
    )
    url = (
        "https://image.pollinations.ai/prompt/"
        f"{urllib.parse.quote(prompt_text)}?width=800&height=400&nologo=true"
    )
    if st.button("Generate Conceptual 3D Architectural Render"):
        with st.spinner("Generating 3D architectural render via AI..."):
            st.session_state["render_bytes"] = fetch_render(url)
            st.session_state["render_caption"] = f"Concept render: {struct_type}"
            st.session_state["render_failed"] = st.session_state["render_bytes"] is None

    if st.session_state.get("render_failed"):
        st.warning("The render service is slow or unavailable right now. Please try again in a moment.")
    elif st.session_state.get("render_bytes"):
        st.image(st.session_state["render_bytes"], caption=st.session_state.get("render_caption"), width="stretch")


def render_assistant_page(api_key: str) -> None:
    st.header("Daily Site Assistant & Weather-Aware Advisory")
    st.caption("Site environmental protocols and construction engineering knowledge assistant")

    st.subheader("🌤️ Weather-Aware Site Safety Protocol Generator")
    weather = st.selectbox(
        "Current Site Weather Condition",
        ["Normal / Clear Skies", "High Winds (>40 km/h)", "Heavy Rain / Monsoon", "Extreme Heat (>42°C)"],
    )
    if weather == "High Winds (>40 km/h)":
        st.error("⚠️ **CRITICAL ADVISORY:** Suspend all tower crane operations, high-altitude glazing and roof "
                 "sheet installation. Secure loose materials on elevated slabs and scaffolding.")
    elif weather == "Heavy Rain / Monsoon":
        st.warning("⚡ **SAFETY ADVISORY:** Inspect excavation slopes for instability, clear drains and run dewatering "
                   "pumps. Halt outdoor electrical connections (electrocution risk), cover cement and fresh concrete.")
    elif weather == "Extreme Heat (>42°C)":
        st.info("🌡️ **HEALTH & CURING ADVISORY:** Enforce 15-minute hydration breaks every 2 hours and shaded rest areas. "
                "Start wet-curing fresh slabs immediately (IS 456) to prevent plastic shrinkage cracking; pour concrete "
                "early morning or at night.")
    else:
        st.success("✅ **NORMAL PROTOCOL:** Standard site activities permitted. Maintain PPE compliance and daily "
                   "toolbox talks.")

    st.divider()
    st.subheader("💬 Interactive Construction Engineering Assistant")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [{
            "role": "assistant",
            "content": "Hello! I'm your construction site assistant. Ask about IS 456 curing, safety protocols, "
                       "material ratios or project scheduling.",
        }]

    if st.button("🗑️ Clear chat"):
        st.session_state.pop("chat_history")
        st.rerun()

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    user_input = st.chat_input("Ask a construction or engineering question...")
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)
        with st.chat_message("assistant"):
            with st.spinner("Consulting construction knowledge base..."):
                reply = chat_reply(api_key, st.session_state.chat_history)
            st.write(reply)
        st.session_state.chat_history.append({"role": "assistant", "content": reply})


# -----------------------------------------------------------------------------
# 5. SIDEBAR + ROUTER
# -----------------------------------------------------------------------------
PAGES = {
    "🛡️ Site Safety & PPE Audit": "ppe",
    "🔍 Crack Diagnostics": "crack",
    "📊 Planning & Valuation": "plan",
    "🤖 Site Assistant & Advisory": "assist",
}


def render_sidebar() -> tuple:
    with st.sidebar:
        st.title("🏗️ Construction AI")
        st.caption("SkillWallet Capstone - Project 1")
        st.divider()

        st.markdown("### Navigation")
        page = st.radio("Go to", list(PAGES.keys()), label_visibility="collapsed")

        st.divider()
        api_key = st.text_input(
            "Google Gemini API Key", type="password",
            help="Used only in this session and never stored. Leave blank for demo mode.",
        ).strip()
        if api_key and GENAI_AVAILABLE:
            st.success("Live AI mode enabled", icon="✅")
        elif api_key and not GENAI_AVAILABLE:
            st.error("google-genai is not installed. Running in demo mode.", icon="⚠️")
        else:
            st.info("Demo mode: no API key provided. Pre-built intelligent responses are shown.", icon="ℹ️")

        st.divider()
        st.markdown("### Architecture Overview")
        st.markdown(
            f"- **Frontend:** Streamlit\n"
            f"- **AI Core:** {MODEL_NAME} (multimodal) with offline fallback\n"
            f"- **Standards:** OSHA and IS 456\n"
            f"- **Data Contract:** Validated JSON schemas\n"
            f"- **Storage:** None (stateless, session only)"
        )
    return PAGES[page], api_key


def main() -> None:
    st.markdown('<div class="main-title">Multimodal Construction Intelligence Platform</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-title">Real-time site safety, structural diagnostics, cost valuation and AI advisory engine</div>',
        unsafe_allow_html=True,
    )

    page, api_key = render_sidebar()

    try:
        if page == "ppe":
            render_ppe_page(api_key)
        elif page == "crack":
            render_crack_page(api_key)
        elif page == "plan":
            render_planning_page()
        else:
            render_assistant_page(api_key)
    except Exception as exc:  # last-resort guard so the UI never shows a raw traceback
        st.error(f"Something went wrong: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
