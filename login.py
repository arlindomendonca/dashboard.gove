"""
login.py — Entry point do sistema.
Exibe tela de login. Após autenticar, redireciona ao dashboard.
"""
import streamlit as st
from supabase_auth import login, is_authenticated, get_user, logout

st.set_page_config(
    page_title="Login — Sistema de Atendimentos",
    page_icon="🏛️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── CSS ──────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Fundo geral */
    .stApp { background: radial-gradient(ellipse at top, #1a1d2e 0%, #0f1117 70%); }

    /* Esconde sidebar e toggle na tela de login */
    [data-testid="stSidebar"],
    [data-testid="collapsedControl"] { display: none !important; }

    /* Card de login */
    .card {
        background: linear-gradient(145deg, #1e2130, #252a3d);
        border: 1px solid #2e3450;
        border-radius: 20px;
        padding: 44px 40px 36px 40px;
        box-shadow: 0 20px 60px rgba(0,0,0,0.5);
    }
    .card-logo   { text-align:center; font-size:60px; margin-bottom:10px; }
    .card-title  { text-align:center; font-size:24px; font-weight:800;
                   color:#e2e8f0; margin-bottom:4px; }
    .card-sub    { text-align:center; font-size:13px; color:#64748b;
                   margin-bottom:34px; }
    .divider     { border:none; border-top:1px solid #2e3450; margin:22px 0; }
    .footer-txt  { text-align:center; font-size:11px; color:#374151; margin-top:18px; }

    /* Inputs */
    div[data-testid="stTextInput"] input {
        background: #13162280 !important;
        border: 1px solid #2e3450 !important;
        color: #e2e8f0 !important;
        border-radius: 10px !important;
        padding: 10px 14px !important;
        font-size: 14px !important;
    }
    div[data-testid="stTextInput"] input:focus {
        border-color: #6366f1 !important;
        box-shadow: 0 0 0 3px rgba(99,102,241,0.15) !important;
    }

    /* Botão primário */
    button[kind="primaryFormSubmit"] {
        background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%) !important;
        color: white !important; border: none !important;
        border-radius: 10px !important; height: 48px !important;
        font-size: 15px !important; font-weight: 700 !important;
        letter-spacing: 0.3px !important;
        transition: all 0.2s !important;
    }
    button[kind="primaryFormSubmit"]:hover { opacity: 0.92 !important; }
</style>
""", unsafe_allow_html=True)

# ── Já logado → redireciona ──────────────────────────────────────
if is_authenticated():
    u = get_user()
    nome = u.get("nome", u.get("email", "Usuário"))
    st.markdown(f"""
    <div style="text-align:center;margin-top:80px">
        <div style="font-size:52px">🏛️</div>
        <div style="font-size:20px;font-weight:700;color:#e2e8f0;margin-top:10px">
            Bem-vindo, {nome}!
        </div>
        <div style="font-size:13px;color:#64748b;margin-top:4px">
            Você já está autenticado.
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("📊 Dashboard", use_container_width=True):
            st.switch_page("pages/1_📊_Dashboard.py")
    with c2:
        if st.button("🔴 Em Aberto", use_container_width=True):
            st.switch_page("pages/2_🔴_Abertos.py")

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚪 Sair", use_container_width=True):
        logout()
        st.rerun()
    st.stop()

# ── Formulário de Login ──────────────────────────────────────────
_, mid, _ = st.columns([1, 2.4, 1])
with mid:
    st.markdown("""
    <div class="card">
        <div class="card-logo">🏛️</div>
        <div class="card-title">Sistema de Atendimentos</div>
        <div class="card-sub">Prefeitura de Rio Verde · Acesso Restrito</div>
    </div>
    """, unsafe_allow_html=True)

    # Formulário dentro de um espaço separado (sem o card para não conflitar)
    with st.form("form_login", clear_on_submit=False):
        st.markdown("<br>", unsafe_allow_html=True)
        email = st.text_input("E-mail", placeholder="seu@email.com.br")
        senha = st.text_input("Senha", type="password", placeholder="••••••••")
        st.markdown("<br>", unsafe_allow_html=True)
        btn   = st.form_submit_button("Entrar →", use_container_width=True)

    if btn:
        if not email.strip() or not senha:
            st.error("⚠️ Preencha e-mail e senha.")
        else:
            with st.spinner("Autenticando..."):
                res = login(email.strip().lower(), senha)

            if res["success"]:
                auth_user = res["user"]

                # Monta dados do usuário na sessão
                user_data = {
                    "id":    auth_user.get("id", ""),
                    "email": auth_user.get("email", email),
                    "nome":  auth_user.get("user_metadata", {}).get(
                                 "nome",
                                 email.split("@")[0].replace(".", " ").title()
                             ),
                }
                st.session_state["access_token"]  = res["access_token"]
                st.session_state["refresh_token"] = res["refresh_token"]
                st.session_state["user_data"]     = user_data

                st.success(f"✅ Bem-vindo, {user_data['nome']}!")
                st.rerun()
            else:
                st.error(f"❌ {res['error']}")

    st.markdown("""
    <div class="footer-txt">
        Problemas de acesso? Contate o administrador do sistema.
    </div>
    """, unsafe_allow_html=True)
