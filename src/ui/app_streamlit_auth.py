import html
import os
import requests
import streamlit as st
from pypdf import PdfReader
from io import BytesIO
from src.auth.auth import init_db, create_user, authenticate_user, get_user_email, log_query, get_user_stats

st.set_page_config(page_title="Tessera Agentic RAG", layout="wide")

# Initialize database
init_db()

# Color scheme: Blue/Brown theme
st.markdown("""
<style>
:root {
  --primary-blue: #1e40af;
  --primary-brown: #78350f;
  --light-blue: #3b82f6;
  --light-brown: #92400e;
  --dark-bg: #0f172a;
  --card-bg: #1e293b;
  --text-light: #e2e8f0;
  --text-muted: #94a3b8;
}

.stApp {
  background-color: #0f172a;
  color: #e2e8f0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

[data-testid="stSidebar"] {
  background-color: #1e293b;
  border-right: 2px solid #3b82f6;
}

[data-testid="stSidebar"] * {
  color: #e2e8f0;
}

[data-testid="stSidebar"] input,
[data-testid="stSidebar"] select {
  background-color: #0a0e27 !important;
  border: 2px solid #10b981 !important;
  color: #e2e8f0 !important;
}

[data-testid="stSidebar"] input::placeholder {
  color: #64748b !important;
}

.stSelectbox > div > div {
  background-color: #0a0e27 !important;
}

.stSelectbox > div > div > div {
  background-color: #0a0e27 !important;
  border: 2px solid #10b981 !important;
  color: #e2e8f0 !important;
}

.stSelectbox label,
.stCheckbox label {
  color: #e2e8f0 !important;
}

.stButton > button {
  background: linear-gradient(135deg, #3b82f6 0%, #1e40af 100%);
  color: #ffffff;
  font-weight: 600;
  border-radius: 10px;
  border: none;
}

.stButton > button:hover {
  background: linear-gradient(135deg, #1e40af 0%, #1e3a8a 100%);
}

.login-container {
  max-width: 400px;
  margin: 50px auto;
  padding: 30px;
  background: linear-gradient(135deg, rgba(30, 64, 175, 0.1), rgba(120, 53, 15, 0.1));
  border: 2px solid #3b82f6;
  border-radius: 15px;
}

.auth-header {
  text-align: center;
  margin-bottom: 30px;
  color: #3b82f6;
}

.metrics-card {
  background: linear-gradient(135deg, #1e40af 0%, #78350f 100%);
  border: 1px solid #3b82f6;
  border-radius: 12px;
  padding: 15px;
  margin-bottom: 12px;
  color: #e2e8f0;
}

.answer-card {
  background: #1e293b;
  border: 1px solid #3b82f6;
  border-radius: 12px;
  padding: 16px 18px;
  margin-bottom: 12px;
  color: #e2e8f0;
  font-size: 15px;
  line-height: 1.5;
}

.chat-bubble {
  border: 1px solid #3b82f6;
  background: #1e293b;
  border-radius: 16px;
  padding: 14px 16px;
}

.source-chip {
  padding: 4px 8px;
  border-radius: 8px;
  background: #1e40af;
  border: 1px solid #3b82f6;
  font-size: 12px;
  color: #e2e8f0;
}

.user-stats {
  background: linear-gradient(135deg, #1e40af 0%, #78350f 100%);
  border: 2px solid #3b82f6;
  border-radius: 12px;
  padding: 15px;
  margin: 15px 0;
  color: #e2e8f0;
}

.health-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  font-size: 14px;
  background: rgba(59, 130, 246, 0.1);
  border: 1px solid #3b82f6;
  border-radius: 8px;
  color: #e2e8f0;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}

.dot.online {
  background: #10b981;
  box-shadow: 0 0 8px rgba(16, 185, 129, 0.5);
}

.dot.offline {
  background: #ef4444;
  box-shadow: 0 0 8px rgba(239, 68, 68, 0.5);
}

.app-header {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 0 8px 0;
  border-bottom: 2px solid #3b82f6;
  margin-bottom: 18px;
}

.logo-mark {
  width: 44px;
  height: 44px;
  background: linear-gradient(135deg, #3b82f6 0%, #1e40af 100%);
  color: #ffffff;
  font-weight: 700;
  font-size: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
}

.wordmark {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: #e2e8f0;
  line-height: 1.1;
}

.tagline {
  font-size: 14px;
  color: #94a3b8;
}
</style>
""", unsafe_allow_html=True)

# Session state initialization
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "user_email" not in st.session_state:
    st.session_state.user_email = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "health" not in st.session_state:
    st.session_state.health = None
# Backend session token, derived automatically at login. The user never enters it.
if "api_token" not in st.session_state:
    st.session_state.api_token = None
if "api_base" not in st.session_state:
    st.session_state.api_base = os.environ.get("TESSERA_API_BASE", "http://localhost:8000")


def _extract_pdf_text(pdf_bytes):
    try:
        pdf = PdfReader(BytesIO(pdf_bytes))
        text = ""
        for page in pdf.pages:
            # extract_text() returns None for image-only or empty pages;
            # concatenating None raises TypeError, so coerce to "" first.
            text += page.extract_text() or ""
        return text if text.strip() else None
    except Exception:
        return None


def _extract_detail(resp):
    try:
        detail = resp.json().get("detail")
        if isinstance(detail, list):
            return "; ".join(str(d) for d in detail)
        return str(detail if detail else resp.text[:300])
    except Exception:
        return resp.text[:300] or "No response body"


def health_check(api_base):
    try:
        resp = requests.get(f"{api_base}/health", timeout=5)
        if resp.status_code == 200 and resp.json().get("status") == "ok":
            return True, None
        return False, f"HTTP {resp.status_code}: {_extract_detail(resp)}"
    except requests.exceptions.Timeout:
        return False, "Request timed out after 5 seconds."
    except requests.exceptions.ConnectionError:
        return False, "Connection failed: could not reach the API."
    except requests.exceptions.RequestException as exc:
        return False, f"Request failed: {exc}"


def login_backend(api_base, email, password):
    """Exchange credentials for a backend session token.

    The frontend authenticates against the same PBKDF2 store the API uses, then
    calls /auth/login to obtain the HMAC session token the API expects on every
    request. The user never sees or types this token: it is derived from their
    login and held in session state, so each account automatically talks to its
    own tenant workspace.
    """
    try:
        resp = requests.post(
            f"{api_base}/auth/login",
            json={"email": email, "password": password},
            timeout=10,
        )
    except requests.exceptions.ConnectionError:
        return None, "Connection failed: could not reach the API."
    except requests.exceptions.RequestException as exc:
        return None, f"Request failed: {exc}"

    if resp.status_code != 200:
        return None, _extract_detail(resp)
    try:
        return resp.json().get("token"), None
    except ValueError:
        return None, "Login response is not valid JSON."


def upload_file(api_base, token, file_obj):
    url = f"{api_base}/upload"
    headers = {"Authorization": f"Bearer {token}"}

    file_content = file_obj.getvalue()
    file_name = file_obj.name

    if file_name.lower().endswith('.pdf'):
        pdf_text = _extract_pdf_text(file_content)
        if pdf_text is None:
            return None, "Failed to extract text from PDF"
        file_content = pdf_text.encode('utf-8')
        file_name = file_name.rsplit('.', 1)[0] + '.txt'

    try:
        resp = requests.post(
            url,
            headers=headers,
            files={"file": (file_name, file_content, "text/plain")},
            timeout=120,
        )
    except requests.exceptions.Timeout:
        return None, "Request timed out after 120 seconds."
    except requests.exceptions.ConnectionError:
        return None, "Connection failed: could not reach the API."
    except requests.exceptions.RequestException as exc:
        return None, f"Request failed: {exc}"

    if resp.status_code != 200:
        detail = _extract_detail(resp)
        if resp.status_code == 401:
            return None, "Unauthorized: check your bearer token"
        return None, f"HTTP {resp.status_code}: {detail}"

    try:
        return resp.json(), None
    except ValueError:
        return None, "Response is not valid JSON."


def ask_question(api_base, token, question, top_k, force_route=None, run_eval=False, expected_output=None):
    url = f"{api_base}/ask"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"question": question, "top_k": top_k, "run_eval": run_eval}
    if expected_output and expected_output.strip():
        payload["expected_output"] = expected_output.strip()
    if force_route and force_route != "auto":
        payload["force_route"] = force_route
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=180)
    except requests.exceptions.Timeout:
        return None, "Request timed out after 60 seconds."
    except requests.exceptions.ConnectionError:
        return None, "Connection failed: could not reach the API."
    except requests.exceptions.RequestException as exc:
        return None, f"Request failed: {exc}"

    if resp.status_code != 200:
        detail = _extract_detail(resp)
        if resp.status_code == 401:
            return None, "Unauthorized: check your bearer token"
        return None, f"HTTP {resp.status_code}: {detail}"

    try:
        return resp.json(), None
    except ValueError:
        return None, "Response is not valid JSON."


def get_budget(api_base):
    url = f"{api_base}/budget"

    try:
        resp = requests.get(url, timeout=10)
    except requests.exceptions.Timeout:
        return None, "Budget request timed out."
    except requests.exceptions.ConnectionError:
        return None, "Could not connect to the API."
    except requests.exceptions.RequestException as exc:
        return None, f"Budget request failed: {exc}"

    if resp.status_code != 200:
        return None, f"HTTP {resp.status_code}"

    try:
        return resp.json(), None
    except ValueError:
        return None, "Response is not valid JSON."


# LOGIN PAGE
if st.session_state.user_id is None:
    st.markdown('<div class="auth-header"><h1>🔐 Tessera</h1><p>Secure Multi-Tenant RAG Console</p></div>',
                unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        st.markdown("### 📝 Sign Up")
        signup_email = st.text_input("Email", key="signup_email", placeholder="your@email.com")
        signup_password = st.text_input("Password", type="password", key="signup_password", placeholder="Min 6 characters")
        signup_confirm = st.text_input("Confirm Password", type="password", key="signup_confirm", placeholder="Confirm password")

        if st.button("Create Account", use_container_width=True):
            if not signup_email or not signup_password or not signup_confirm:
                st.error("All fields required")
            elif signup_password != signup_confirm:
                st.error("Passwords do not match")
            else:
                success, msg = create_user(signup_email, signup_password)
                if success:
                    st.success(msg)
                    st.info("Now login with your credentials")
                else:
                    st.error(msg)
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        st.markdown("### 🔑 Login")
        login_email = st.text_input("Email", key="login_email", placeholder="your@email.com")
        login_password = st.text_input("Password", type="password", key="login_password", placeholder="Your password")

        if st.button("Login", use_container_width=True):
            if not login_email or not login_password:
                st.error("Email and password required")
            else:
                success, msg, user_id = authenticate_user(login_email, login_password)
                if not success:
                    st.error(msg)
                else:
                    # Fetch the backend session token so every request this user
                    # makes is authorized automatically against their own tenant.
                    token, token_err = login_backend(
                        st.session_state.api_base, login_email, login_password
                    )
                    if token_err:
                        st.error(f"Signed in, but the API is unreachable: {token_err}")
                    else:
                        st.session_state.user_id = user_id
                        st.session_state.user_email = login_email
                        st.session_state.api_token = token
                        st.success(msg)
                        st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

else:
    # MAIN APP (After Login)
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state.user_email}")
        if st.button("🚪 Logout"):
            st.session_state.user_id = None
            st.session_state.user_email = None
            st.session_state.api_token = None
            st.session_state.chat_history = []
            st.rerun()

        st.markdown("---")
        st.markdown("### Connection")
        api_base = st.text_input("API base URL", value=st.session_state.api_base)
        st.session_state.api_base = api_base
        # The session token is derived at login and used automatically. Every user
        # gets the same request path; their tenant is isolated by their identity,
        # not by a token they have to paste in.
        api_token = st.session_state.api_token
        st.caption("🔒 Signed in. Your workspace is isolated automatically.")

        if st.button("Check health"):
            ok, err = health_check(api_base)
            st.session_state.health = "online" if ok else "offline"
            if ok:
                st.success("✓ Connected")
            else:
                st.error(f"✗ {err}")

        st.markdown("### Retrieval Configuration")
        retriever_type = st.selectbox(
            "Retriever Type",
            ["vector", "direct"],
            help="vector: Search local docs | direct: No retrieval"
        )

        st.markdown("### Search Options")
        enable_web_search = st.checkbox("Enable web search", value=False)

        st.markdown("### Generation Settings")
        retriever_top_k = st.slider("Top-K (documents)", min_value=1, max_value=20, value=5)

        st.markdown("### Advanced Settings")
        enable_self_check = st.checkbox("Self-checking (auto-refinement)", value=True)
        show_trace = st.checkbox("Show execution trace", value=False)

        st.markdown("---")
        stats = get_user_stats(st.session_state.user_id)
        st.markdown("### 📊 Your Statistics")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Queries", stats["total_queries"])
        with col2:
            st.metric("Tokens", f"{stats['total_tokens']:,}")
        with col3:
            st.metric("Cost", f"${stats['total_cost_usd']:.4f}")
        st.markdown("---")
        st.markdown("### 💰 Cost Controls")
        budget_data, budget_err = get_budget(api_base)
        if budget_err:
            st.caption(f"Budget info unavailable: {budget_err}")
        else:
            budget_data = budget_data or {}
            max_tokens = budget_data.get("max_output_tokens", "unknown")
            daily_cap = budget_data.get("daily_spend_usd_cap", 0) or 0
            if daily_cap > 0:
                daily_cap_label = f"${daily_cap:.2f}"
            else:
                daily_cap_label = "disabled"
            spent = budget_data.get("spend_so_far_usd", 0.0) or 0.0
            remaining = budget_data.get("spend_remaining_usd")
            st.caption(f"Per-answer output cap: {max_tokens} tokens")
            st.caption(f"Daily spend cap: {daily_cap_label}")
            if remaining is not None:
                st.caption(f"Spent this run: ${spent:.4f} (remaining ${remaining:.4f})")
            else:
                st.caption(f"Spent this run: ${spent:.4f}")

    st.markdown(
        '<div class="app-header">'
        '<div class="logo-mark">T</div>'
        '<div>'
        '<div class="wordmark">Tessera</div>'
        '<div class="tagline">Multi-tenant agentic RAG console.</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    tab_ask, tab_upload = st.tabs(["Ask", "Upload"])

    with tab_ask:
        if not api_token:
            st.warning("⚠️ The API was unreachable at login. Log out and back in once it is running.")
        else:
            web_indicator = "🌐 Web search enabled" if enable_web_search else "📄 Local only"
            st.info(f"🔍 Retriever: **{retriever_type}** | {web_indicator} | 📊 Top-K: **{retriever_top_k}**")

            if st.session_state.chat_history:
                for entry in st.session_state.chat_history:
                    st.markdown(f"**Q:** {entry['question']}")
                    st.markdown(f"**A:** {entry['answer']}")

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.caption(f"Route: {entry.get('route', 'unknown')}")
                    with col2:
                        st.caption(f"Latency: {entry.get('latency_ms', 0):.0f}ms")
                    with col3:
                        st.caption(f"Cost: ${entry.get('estimated_cost_usd', 0):.6f}")

                    if entry.get("sources"):
                        st.caption(f"Sources: {', '.join(entry['sources'])}")

                    if entry.get("eval") and isinstance(entry.get("eval"), dict):
                        eval_data = entry["eval"]
                        with st.expander("DeepEval scores"):
                            if eval_data.get("enabled") is False:
                                st.caption(eval_data.get("reason", "DeepEval unavailable"))
                            else:
                                metrics = eval_data.get("metrics", {})
                                if metrics:
                                    for metric_name, metric in metrics.items():
                                        display_name = metric_name.replace("_", " ").title()
                                        if isinstance(metric, dict) and "score" in metric:
                                            score = metric.get("score")
                                            threshold = metric.get("threshold")
                                            passed = metric.get("passed")
                                            mark = "&#9989;" if passed else "&#10060;"
                                            st.markdown(
                                                f"**{display_name}:** {score:.3f} "
                                                f"(threshold {threshold}) {mark}"
                                            )
                                            reason = metric.get("reason")
                                            if reason:
                                                st.caption(reason)
                                        elif isinstance(metric, dict) and "status" in metric:
                                            status = metric.get("status")
                                            reason = metric.get("reason", "")
                                            st.caption(f"{display_name}: {status} - {reason}")
                                        elif isinstance(metric, dict) and "error" in metric:
                                            error = metric.get("error", "")
                                            st.caption(f"{display_name}: error - {error}")
                                else:
                                    st.caption("No metrics returned.")
                    st.markdown("---")
            else:
                st.info("No questions yet. Ask below!")

            run_eval = st.checkbox(
                "Evaluate answer quality (DeepEval)",
                value=False,
                help="Run DeepEval metrics on the answer. Increases latency significantly."
            )
            if run_eval:
                expected = st.text_area(
                    "Expected answer (optional, improves correctness metrics)",
                    value=""
                )
            else:
                expected = ""

            question = st.chat_input("Ask a question about your documents")
            if question:
                with st.spinner("Processing..."):
                    if retriever_type == "direct":
                        force_route = "direct"
                    elif enable_web_search:
                        force_route = "web"
                    else:
                        force_route = "vector"

                    result, err = ask_question(
                        api_base,
                        api_token,
                        question,
                        retriever_top_k,
                        force_route=force_route,
                        run_eval=run_eval,
                        expected_output=(expected.strip() or None),
                    )

                if err:
                    st.error(f"❌ {err}")
                else:
                    entry = {
                        "question": question,
                        "answer": result.get("answer", ""),
                        "route": result.get("route", ""),
                        "sources": result.get("sources", []),
                        "latency_ms": result.get("latency_ms"),
                        "tokens": result.get("tokens", {}),
                        "estimated_cost_usd": result.get("estimated_cost_usd"),
                        "trace": result.get("trace", []),
                        "eval": result.get("eval"),
                    }
                    st.session_state.chat_history.append(entry)

                    # Log to database
                    tokens = result.get("tokens", {}).get("total", 0)
                    cost = result.get("estimated_cost_usd", 0)
                    log_query(st.session_state.user_id, question, entry["answer"], entry["route"], tokens, cost)

                    st.rerun()

    with tab_upload:
        if not api_token:
            st.warning("⚠️ The API was unreachable at login. Log out and back in once it is running.")
        else:
            uploaded_file = st.file_uploader("Choose a .md, .txt, or .pdf file", type=["md", "txt", "pdf"])

            if st.button("Upload and re-index"):
                if uploaded_file is None:
                    st.warning("Please choose a file first")
                else:
                    with st.spinner("Uploading and indexing..."):
                        result, err = upload_file(api_base, api_token, uploaded_file)
                    if err:
                        st.error(f"❌ {err}")
                    else:
                        st.success(f"✓ Uploaded: {result.get('filename')}")
                        st.json(result)
