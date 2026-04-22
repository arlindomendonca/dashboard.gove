"""
supabase_logs.py
Salva e lê histórico/logs de atendimentos no Supabase.
Tabela: atendimento_logs
"""
import requests
import streamlit as st
import pandas as pd
from datetime import datetime
from supabase_auth import _url, _h_auth

REST = lambda: f"{_url()}/rest/v1"

# ─────────────────────────────────────────
# Escrita: salva snapshot de atendimentos
# ─────────────────────────────────────────
def salvar_snapshot(df: pd.DataFrame, fonte: str = "api_gove") -> bool:
    """
    Salva um snapshot dos atendimentos em aberto no Supabase.
    Chame periodicamente (ex: a cada sync da API).

    Parâmetros:
        df     : DataFrame com atendimentos em aberto
        fonte  : identificador da origem dos dados
    """
    token = st.session_state.get("access_token", "")
    if not token or df.empty:
        return False

    # Prepara registros
    registros = []
    for _, row in df.iterrows():
        registros.append({
            "protocolo":        str(row.get("id", row.get("protocolo", ""))),
            "status":           str(row.get("status", "aberto")),
            "setor":            str(row.get("sector", row.get("setor", ""))),
            "atendente":        str(row.get("agent", row.get("atendente", ""))),
            "aberto_em":        _fmt_dt(row.get("started_at", row.get("aberto_em"))),
            "encerrado_em":     _fmt_dt(row.get("finished_at", row.get("encerrado_em"))),
            "tempo_util_min":   _safe_float(row.get("_min_aberto")),
            "faixa_tempo":      str(row.get("Faixa", "")),
            "fonte":            fonte,
            "snapshot_em":      datetime.utcnow().isoformat(),
        })

    try:
        r = requests.post(
            f"{REST()}/atendimento_logs",
            json=registros,
            headers={**_h_auth(token), "Prefer": "resolution=merge-duplicates"},
            timeout=20,
        )
        return r.status_code in (200, 201)
    except Exception:
        return False


def buscar_historico(
    protocolo: str | None = None,
    data_ini: str | None = None,  # ISO: "2026-04-01"
    data_fim: str | None = None,
    limit: int = 500,
) -> pd.DataFrame:
    """
    Lê histórico de logs do Supabase.
    Retorna DataFrame ordenado por snapshot_em desc.
    """
    token = st.session_state.get("access_token", "")
    if not token:
        return pd.DataFrame()

    params = f"select=*&order=snapshot_em.desc&limit={limit}"
    if protocolo:
        params += f"&protocolo=eq.{protocolo}"
    if data_ini:
        params += f"&snapshot_em=gte.{data_ini}"
    if data_fim:
        params += f"&snapshot_em=lte.{data_fim}T23:59:59"

    try:
        r = requests.get(
            f"{REST()}/atendimento_logs?{params}",
            headers=_h_auth(token),
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            return pd.DataFrame(data) if data else pd.DataFrame()
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def buscar_metricas_diarias() -> pd.DataFrame:
    """
    Retorna métricas diárias agrupadas (total, críticos, vencidos por dia).
    Usa a view v_metricas_diarias criada no Supabase.
    """
    token = st.session_state.get("access_token", "")
    if not token:
        return pd.DataFrame()

    try:
        r = requests.get(
            f"{REST()}/v_metricas_diarias?select=*&order=dia.desc&limit=30",
            headers=_h_auth(token),
            timeout=15,
        )
        if r.status_code == 200:
            return pd.DataFrame(r.json())
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


# ─────────────────────────────────────────
# Helpers internos
# ─────────────────────────────────────────
def _fmt_dt(val) -> str | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        if isinstance(val, (datetime, pd.Timestamp)):
            return val.isoformat()
        return str(val)
    except Exception:
        return None

def _safe_float(val) -> float | None:
    try:
        v = float(val)
        return None if pd.isna(v) else round(v, 2)
    except Exception:
        return None
