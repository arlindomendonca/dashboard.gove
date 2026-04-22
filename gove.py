"""
gove.py — Wrapper da API Gove v2.
Estrutura baseada no JSON real:
  /v2/chats       → { data: [{id, recipient, started_at, finished_at, agent, sector, rating}] }
  /v2/chats/{id}/messages → { data: [{uuid, channel, recipient, body, sent_at, attachment, ...}] }

recipient no chat  = telefone do contribuinte (string)
recipient na msg   = quem recebeu:
  - igual ao recipient do chat → mensagem enviada pelo SISTEMA/ATENDENTE ao contribuinte
  - diferente → mensagem enviada pelo CONTRIBUINTE ao sistema
"""
import os
import requests
import streamlit as st
import pandas as pd

# ─────────────────────────────────────────────
# Credenciais
# ─────────────────────────────────────────────
def _token() -> str:
    try:    return st.secrets["GOVE_TOKEN"]
    except: return os.environ.get("GOVE_TOKEN", "")

def _base() -> str:
    try:    return st.secrets.get("GOVE_BASE_URL", "https://api.gove.digital/v2")
    except: return os.environ.get("GOVE_BASE_URL", "https://api.gove.digital/v2")

def _h() -> dict:
    return {
        "Authorization": f"Bearer {_token()}",
        "Accept":        "application/json",
        "Content-Type":  "application/json",
    }

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def _str(v) -> str | None:
    if v is None: return None
    s = str(v).strip()
    return s if s and s.lower() not in ("none","nan","null","") else None

def _dt_fmt(v, fmt="%d/%m/%Y %H:%M") -> str:
    if not v: return "—"
    try:
        return pd.to_datetime(v, errors="coerce").strftime(fmt)
    except:
        return str(v)[:16] if v else "—"

def _dt_iso(v) -> str | None:
    if not v: return None
    try:
        return pd.to_datetime(v, errors="coerce").isoformat()
    except:
        return None

def _fetch(url: str, params: dict | None = None) -> dict:
    """Faz GET e retorna dict bruto ou {'error': msg}."""
    try:
        r = requests.get(url, headers=_h(), params=params or {}, timeout=30)
    except requests.exceptions.ConnectionError:
        return {"error": "Sem conexão com a API Gove."}
    except requests.exceptions.Timeout:
        return {"error": "Timeout ao consultar a API Gove."}
    except Exception as e:
        return {"error": str(e)}

    if r.status_code == 401:
        return {"error": "Token inválido (401)."}
    if r.status_code != 200:
        return {"error": f"HTTP {r.status_code}: {r.text[:200]}"}
    try:
        return r.json()
    except:
        return {"error": "Resposta não é JSON válido."}


# ─────────────────────────────────────────────
# Parsers baseados na estrutura real da API
# ─────────────────────────────────────────────
def _parse_chat(c: dict) -> dict:
    """Converte um item de /v2/chats para dict normalizado."""
    agent  = c.get("agent")  or {}
    sector = c.get("sector") or {}

    return {
        # Identificação
        "id":                  str(c.get("id", "")),
        "recipient":           _str(c.get("recipient")),  # telefone do contribuinte
        # Agente
        "agent_uuid":          _str(agent.get("uuid")),
        "agent_name":          _str(agent.get("name")),
        "agent_email":         _str(agent.get("email")),
        "agent_created_at":    _dt_iso(agent.get("created_at")),
        # Setor
        "sector_uuid":         _str(sector.get("uuid")),
        "sector_name":         _str(sector.get("name")),
        "sector_acronym":      _str(sector.get("acronym")),
        # Datas
        "started_at":          _dt_iso(c.get("started_at")),
        "finished_at":         _dt_iso(c.get("finished_at")),
        # Extras
        "rating":              c.get("rating"),
        # Display (formatados para a tabela)
        "_started_fmt":        _dt_fmt(c.get("started_at")),
        "_finished_fmt":       _dt_fmt(c.get("finished_at")) if c.get("finished_at") else "—",
        "_status":             "Encerrado" if c.get("finished_at") else "Aberto",
    }


def _parse_mensagem(m: dict, recipient_contribuinte: str | None) -> dict:
    """
    Converte uma mensagem para dict normalizado.
    Determina o LADO com base no recipient:
      - Se recipient da msg == recipient do chat → SISTEMA enviou ao contribuinte (lado direito)
      - Caso contrário → CONTRIBUINTE enviou (lado esquerdo)
    """
    recipient_msg = str(m.get("recipient", "")).strip()
    recipient_con = str(recipient_contribuinte or "").strip()

    # Mensagem enviada PELO SISTEMA/ATENDENTE (recipient = telefone do contribuinte)
    if recipient_msg == recipient_con:
        lado = "sistema"   # bolha à direita (enviada pela prefeitura)
    else:
        lado = "contribuinte"  # bolha à esquerda (resposta do cidadão)

    return {
        "uuid":                   _str(m.get("uuid")),
        "channel":                _str(m.get("channel")),
        "recipient":              recipient_msg,
        "lado":                   lado,
        "body":                   _str(m.get("body")) or "",
        "sent_at":                _dt_iso(m.get("sent_at")),
        "sent_at_fmt":            _dt_fmt(m.get("sent_at"), "%d/%m %H:%M"),
        "read_at":                _dt_iso(m.get("read_at")),
        "send_status":            _str(m.get("send_status")),
        "send_status_confirmation": _str(m.get("send_status_confirmation")),
        "attachment":             m.get("attachment"),
    }


# ─────────────────────────────────────────────
# Busca de atendimentos (com cache)
# ─────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def buscar_atendimentos(
    data_ini: str | None = None,
    data_fim: str | None = None,
    protocolo: str | None = None,
    apenas_abertos: bool = True,
    debug: bool = False,
) -> tuple[pd.DataFrame, list[dict]]:
    """
    Retorna (df_exibicao, chats_parsed).
    """
    params: dict = {"order_by": "created_at", "order_direction": "desc"}
    if data_ini:  params["started_at_initial"] = data_ini
    if data_fim:  params["started_at_final"]   = data_fim
    if protocolo: params["id"]                 = protocolo.strip()

    raw = _fetch(f"{_base()}/chats", params)

    if "error" in raw:
        st.error(f"❌ {raw['error']}")
        return pd.DataFrame(), []

    if debug:
        st.info("🔍 Debug — primeiro registro bruto:")
        items = raw.get("data", [])
        if items: st.json(items[0])

    items = raw.get("data", [])
    if not items:
        return pd.DataFrame(), []

    chats = [_parse_chat(c) for c in items]

    # Filtro de abertos
    if apenas_abertos:
        chats = [c for c in chats if not c["finished_at"]]

    if not chats:
        return pd.DataFrame(), []

    # DataFrame de exibição
    rows = [{
        "Protocolo":   c["id"],
        "Contribuinte":c["recipient"] or "—",
        "Atendente":   c["agent_name"] or "—",
        "Setor":       c["sector_name"] or "—",
        "Sigla":       c["sector_acronym"] or "—",
        "Status":      c["_status"],
        "Aberto em":   c["_started_fmt"],
        "Encerrado em":c["_finished_fmt"],
    } for c in chats]

    return pd.DataFrame(rows), chats


# ─────────────────────────────────────────────
# Busca de mensagens (sem cache — sob demanda)
# ─────────────────────────────────────────────
def buscar_mensagens(chat_id: str, recipient_contribuinte: str | None = None) -> list[dict]:
    """
    GET /v2/chats/{id}/messages
    Retorna lista de mensagens parseadas, ordenadas por sent_at ASC.
    """
    raw = _fetch(f"{_base()}/chats/{chat_id}/messages")

    if "error" in raw:
        st.error(f"❌ Erro ao carregar mensagens: {raw['error']}")
        return []

    items = raw.get("data", [])
    if not items:
        return []

    msgs = [_parse_mensagem(m, recipient_contribuinte) for m in items]

    # Ordena cronologicamente (API retorna desc, queremos asc para exibir)
    msgs.sort(key=lambda m: m["sent_at"] or "")

    return msgs
