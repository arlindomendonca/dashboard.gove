"""
supabase_auth.py
Módulo de autenticação Supabase.
Controle de acesso: qualquer usuário autenticado vê tudo.
"""
import os
import requests
import streamlit as st

# ─────────────────────────────────────────
# Credenciais via secrets (nunca no código)
# ─────────────────────────────────────────
def _url() -> str:
    try:
        return st.secrets["SUPABASE_URL"]
    except Exception:
        v = os.environ.get("SUPABASE_URL", "")
        if not v:
            raise RuntimeError("SUPABASE_URL não configurada.")
        return v

def _anon_key() -> str:
    try:
        return st.secrets["SUPABASE_ANON_KEY"]
    except Exception:
        v = os.environ.get("SUPABASE_ANON_KEY", "")
        if not v:
            raise RuntimeError("SUPABASE_ANON_KEY não configurada.")
        return v

def _h_anon() -> dict:
    return {"apikey": _anon_key(), "Content-Type": "application/json"}

def _h_auth(token: str) -> dict:
    return {**_h_anon(), "Authorization": f"Bearer {token}"}

# ─────────────────────────────────────────
# Auth
# ─────────────────────────────────────────
def login(email: str, password: str) -> dict:
    """Autentica via Supabase Auth. Retorna dict com success/error."""
    try:
        r = requests.post(
            f"{_url()}/auth/v1/token?grant_type=password",
            json={"email": email, "password": password},
            headers=_h_anon(), timeout=15,
        )
        d = r.json()
        if r.status_code == 200 and "access_token" in d:
            return {
                "success":       True,
                "access_token":  d["access_token"],
                "refresh_token": d.get("refresh_token", ""),
                "user":          d.get("user", {}),
            }
        msg = d.get("error_description") or d.get("msg") or "Credenciais inválidas."
        return {"success": False, "error": msg}
    except requests.ConnectionError:
        return {"success": False, "error": "Sem conexão com o servidor."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def logout():
    """Limpa a sessão."""
    for k in ["access_token", "refresh_token", "user_data"]:
        st.session_state.pop(k, None)


def is_authenticated() -> bool:
    return bool(st.session_state.get("access_token"))


def get_user() -> dict:
    """Retorna dados do usuário logado."""
    return st.session_state.get("user_data", {})


def require_login():
    """Redireciona para login se não autenticado. Chame no início de cada página."""
    if not is_authenticated():
        st.switch_page("login.py")
        st.stop()
