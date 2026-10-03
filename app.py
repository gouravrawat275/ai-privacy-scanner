import os
import streamlit as st

from modules.credentials import RegisterError, load_or_init_config, register_user, verify_password
from ui import (
    scanner_page,
    live_camera_page,
    consent_page,
    crypto_page,
    pattern_page,
    dashboard_page,
    patent_page
)


st.set_page_config(
    page_title="AI Privacy Scanner & Defense System",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

CUSTOM_CSS = """
<style>
/* Modern Cybernetic Privacy Defense Theme */
.stApp {
    background-color: #090d16;
    color: #e2e8f0;
}
[data-testid="stSidebar"] {
    background-color: #0d1322;
    border-right: 1px solid rgba(56, 189, 248, 0.15);
}
[data-testid="stMetric"] {
    background: linear-gradient(135deg, rgba(17, 24, 39, 0.9), rgba(15, 23, 42, 0.95));
    border: 1px solid rgba(56, 189, 248, 0.25);
    border-radius: 12px;
    padding: 12px 18px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
}
div[data-testid="stMetricValue"] > div {
    color: #38bdf8 !important;
    font-weight: 700 !important;
}
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px 8px 0 0;
    padding: 8px 16px;
    background-color: rgba(30, 41, 59, 0.5);
    color: #94a3b8;
}
.stTabs [aria-selected="true"] {
    background-color: rgba(56, 189, 248, 0.15) !important;
    color: #38bdf8 !important;
    border-bottom: 2px solid #38bdf8 !important;
}
.stButton>button {
    border-radius: 8px;
    font-weight: 600;
    transition: all 0.2s ease-in-out;
}
.stButton>button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(56, 189, 248, 0.35);
}
</style>
"""


def _login_screen():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    st.title("🛡️ AI Privacy Scanner & Defense System")

    config = load_or_init_config()
    usernames = config["credentials"]["usernames"]
    col_login, col_info = st.columns([3, 2])

    with col_login:
        login_tab, signup_tab = st.tabs(["🔐 Log In", "📝 Create Account"])

        with login_tab:
            if not usernames:
                st.info("No account is configured yet. Select Create Account to register the first account.")

            with st.form("login_form"):
                username = st.text_input("Email / username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Log In", type="primary", use_container_width=True)
                if submitted:
                    if verify_password(username, password, config):
                        st.session_state["app_user"] = username
                        st.session_state["app_user_name"] = usernames[username].get("name", username)
                        st.session_state["app_authenticated"] = True
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")

        with signup_tab:
            with st.form("signup_form"):
                first_name = st.text_input("First name")
                last_name = st.text_input("Last name")
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                password_confirm = st.text_input("Confirm password", type="password")
                created = st.form_submit_button("Create Account", type="primary", use_container_width=True)
                if created:
                    try:
                        username = register_user(config, first_name, last_name, email, password, password_confirm)
                        st.session_state["app_user"] = username
                        st.session_state["app_user_name"] = usernames[username]["name"]
                        st.session_state["app_authenticated"] = True
                        st.session_state["app_login_notice"] = "Account created successfully. You are now signed in."
                        st.rerun()
                    except RegisterError as exc:
                        st.error(str(exc))

    with col_info:
        st.markdown("""
        ### 🌟 System Capabilities:
        - **Aspect A:** Cross-Session Behavioral Routine & Commute Pattern Analysis
        - **Aspect B:** Visual Location Inference Independent of Stripped EXIF Metadata
        - **Aspect C:** Per-Person Facial Embedding Consent Gating (Safe Post Workflow)
        - **Aspect D:** AES-256-GCM Cryptographically Reversible Redaction (Stego & Metadata)
        - **Aspect E:** Pre-Capture Live Viewfinder HUD & Actionable Reframing Warnings
        """)


def _authenticated_app():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    login_notice = st.session_state.pop("app_login_notice", None)
    if login_notice:
        st.success(login_notice)
    st.sidebar.title("🛡️ Privacy Defense")
    st.sidebar.caption(f"Operator: `{st.session_state.get('app_user_name', st.session_state['app_user'])}`")

    pages = {
        "🛡️ Multi-Aspect Scanner": scanner_page,
        "📸 Live Viewfinder (Aspect E)": live_camera_page,
        "👥 Consent Registry (Aspect C)": consent_page,
        "🔐 Cryptographic Vault (Aspect D)": crypto_page,
        "📈 Pattern Intelligence (Aspect A)": pattern_page,
        "📊 Intelligence Dashboard": dashboard_page,
        "📜 Patent Architecture & Claims": patent_page,
    }

    current_page_label = st.sidebar.radio("Navigation", list(pages.keys()), index=0)

    st.sidebar.markdown("---")
    st.sidebar.markdown("""
    **Shield Engine Status:**
    - 🟢 Aspect A: Pattern History Active
    - 🟢 Aspect B: Visual Location Inferrer
    - 🟢 Aspect C: Face Consent Gating
    - 🟢 Aspect D: AES-256 Reversible Vault
    - 🟢 Aspect E: Pre-Capture Viewfinder
    """)

    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Log Out", use_container_width=True):
        st.session_state["app_authenticated"] = False
        st.session_state["app_user"] = ""
        st.session_state.pop("app_user_name", None)
        st.rerun()

    # Render selected page
    page_func = pages[current_page_label]
    page_func()


if "app_authenticated" not in st.session_state:
    st.session_state["app_authenticated"] = False

if not st.session_state.get("app_authenticated"):
    _login_screen()
else:
    if "app_user" not in st.session_state or not st.session_state["app_user"]:
        st.session_state["app_authenticated"] = False
        _login_screen()
    else:
        _authenticated_app()

