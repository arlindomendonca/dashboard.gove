"""
pages/1_📊_Dashboard.py
Dashboard histórico (base CSV). Requer login.
"""
import streamlit as st
from supabase_auth import require_login, get_user, logout

require_login()

# ── Header de usuário na sidebar ─────────────────────────────────
u    = get_user()
nome = u.get("nome", u.get("email", "Usuário"))

with st.sidebar:
    st.markdown(f"""
    <div style="background:#1e2130;border:1px solid #2e3450;
                border-radius:10px;padding:11px 14px;margin-bottom:4px">
        <div style="font-size:13px;font-weight:600;color:#e2e8f0">👤 {nome}</div>
        <div style="font-size:11px;color:#64748b">{u.get("email","")}</div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("🔴 Atendimentos em Aberto", use_container_width=True):
        st.switch_page("pages/2_🔴_Abertos.py")

    st.markdown("---")

    if st.button("🚪 Sair", use_container_width=True):
        logout()
        st.switch_page("login.py")

# ── Executa o dashboard existente ────────────────────────────────
exec(open("app_dashboard.py").read())
