"""
supabase_client.py — Integração com Supabase via REST API.
Fluxo: Atendentes → Setores → Atendimentos
(Contribuinte excluído: recipient é só telefone, sem UUID próprio)
"""
import os
import requests
import streamlit as st
from datetime import datetime

def _url() -> str:
    try:    return st.secrets["SUPABASE_URL"]
    except: return os.environ.get("SUPABASE_URL", "")

def _key() -> str:
    try:    return st.secrets["SUPABASE_ANON_KEY"]
    except: return os.environ.get("SUPABASE_ANON_KEY", "")

def _h() -> dict:
    return {
        "apikey":       _key(),
        "Content-Type": "application/json",
        "Prefer":       "resolution=merge-duplicates,return=minimal",
    }

def _rest(table: str) -> str:
    return f"{_url()}/rest/v1/{table}"


# ─────────────────────────────────────────────
# Upsert genérico em lote
# ─────────────────────────────────────────────
def _upsert(table: str, records: list[dict], on_conflict: str) -> dict:
    if not records:
        return {"ok": True, "count": 0}

    # Deduplica pela chave
    seen, unique = set(), []
    for r in records:
        key = r.get(on_conflict)
        if key and key not in seen:
            seen.add(key)
            unique.append(r)

    if not unique:
        return {"ok": True, "count": 0}

    try:
        r = requests.post(
            f"{_rest(table)}?on_conflict={on_conflict}",
            json=unique,
            headers=_h(),
            timeout=30,
        )
        if r.status_code in (200, 201):
            return {"ok": True, "count": len(unique)}
        return {"ok": False, "count": 0,
                "error": f"HTTP {r.status_code}: {r.text[:300]}"}
    except Exception as e:
        return {"ok": False, "count": 0, "error": str(e)}


# ─────────────────────────────────────────────
# Upsert por entidade
# ─────────────────────────────────────────────
def upsert_atendentes(chats: list[dict]) -> dict:
    """Extrai atendentes únicos (por agent_uuid) e faz upsert."""
    now = datetime.utcnow().isoformat()
    records = []
    for c in chats:
        if c.get("agent_uuid"):
            records.append({
                "uuid":       c["agent_uuid"],
                "name":       c.get("agent_name"),
                "email":      c.get("agent_email"),
                "created_at": c.get("agent_created_at"),
                "synced_at":  now,
            })
    return _upsert("atendentes", records, on_conflict="uuid")


def upsert_setores(chats: list[dict]) -> dict:
    """Extrai setores únicos (por sector_uuid) e faz upsert."""
    now = datetime.utcnow().isoformat()
    records = []
    for c in chats:
        if c.get("sector_uuid"):
            records.append({
                "uuid":      c["sector_uuid"],
                "name":      c.get("sector_name"),
                "acronym":   c.get("sector_acronym"),
                "synced_at": now,
            })
    return _upsert("setores", records, on_conflict="uuid")


def upsert_atendimentos(chats: list[dict]) -> dict:
    """Faz upsert dos atendimentos. Atualiza se já existir."""
    now = datetime.utcnow().isoformat()
    records = []
    for c in chats:
        if not c.get("id"):
            continue
        records.append({
            "id":            c["id"],
            "recipient":     c.get("recipient"),       # telefone do contribuinte
            "status":        c.get("_status"),
            "agent_uuid":    c.get("agent_uuid"),
            "sector_uuid":   c.get("sector_uuid"),
            "started_at":    c.get("started_at"),
            "finished_at":   c.get("finished_at"),
            "rating":        c.get("rating"),
            "synced_at":     now,
            "updated_at":    now,
        })
    return _upsert("atendimentos", records, on_conflict="id")


# ─────────────────────────────────────────────
# Pipeline completa
# ─────────────────────────────────────────────
def integrar_tudo(chats: list[dict]) -> dict:
    """
    Integra em ordem: Atendentes → Setores → Atendimentos.
    Retorna resumo por entidade + flag ok global.
    """
    res = {}
    res["atendentes"]   = upsert_atendentes(chats)
    res["setores"]      = upsert_setores(chats)
    res["atendimentos"] = upsert_atendimentos(chats)
    res["ok"] = all(v.get("ok", False) for v in res.values() if isinstance(v, dict))
    return res


# ─────────────────────────────────────────────
# Leitura para Configurações
# ─────────────────────────────────────────────
def contar_registros() -> dict:
    totais = {}
    for tabela, col in [("atendentes","uuid"), ("setores","uuid"), ("atendimentos","id")]:
        try:
            r = requests.get(
                _rest(tabela),
                headers={**_h(), "Prefer": "count=exact"},
                params={"select": col, "limit": "1"},
                timeout=10,
            )
            cr = r.headers.get("content-range", "")
            totais[tabela] = int(cr.split("/")[-1]) if "/" in cr else len(r.json())
        except Exception:
            totais[tabela] = "—"
    return totais


def listar_tabela(tabela: str, limit: int = 200) -> list[dict]:
    try:
        r = requests.get(
            _rest(tabela),
            headers=_h(),
            params={"select": "*", "order": "synced_at.desc", "limit": str(limit)},
            timeout=15,
        )
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []
