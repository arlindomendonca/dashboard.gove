"""
app.py — Gestão de Atendimentos
Painel de conversa via @st.dialog ao clicar na linha.
"""
import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime

from shared_ui import render_header
from gove import buscar_atendimentos, buscar_mensagens
from supabase_client import integrar_tudo

st.set_page_config(
    page_title="Gestão de Atendimentos",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed",
)

render_header("atendimentos")
agora = datetime.now()

# ── CSS extra para o chat ─────────────────────────────────────────
st.markdown("""
<style>
/* Área de mensagens */
.chat-info-bar {
    background: #1e2130; border: 1px solid #2e3450;
    border-radius: 10px; padding: 12px 16px; margin-bottom: 14px;
    font-size: 13px; color: #94a3b8;
    display: flex; flex-wrap: wrap; gap: 12px; align-items: center;
}
.chat-info-bar b { color: #e2e8f0; }

.msg-row {
    display: flex;
    margin-bottom: 8px;
}
.msg-row-sistema       { justify-content: flex-end; }
.msg-row-contribuinte  { justify-content: flex-start; }

.msg-bubble {
    max-width: 72%;
    padding: 10px 14px;
    border-radius: 14px;
    font-size: 13px;
    line-height: 1.55;
    word-break: break-word;
    white-space: pre-wrap;
}
.msg-sistema {
    background: linear-gradient(135deg, #3730a3, #4f46e5);
    color: #ffffff;
    border-bottom-right-radius: 4px;
}
.msg-contribuinte {
    background: #1e2130;
    border: 1px solid #2e3450;
    color: #cbd5e1;
    border-bottom-left-radius: 4px;
}
.msg-meta {
    font-size: 10px;
    margin-top: 4px;
    color: rgba(255,255,255,0.5);
}
.msg-contribuinte .msg-meta { color: #475569; }

.msg-label {
    font-size: 10px; font-weight: 700;
    margin-bottom: 3px; text-transform: uppercase; letter-spacing: 0.5px;
}
.msg-label-sistema      { color: #818cf8; text-align: right; }
.msg-label-contribuinte { color: #64748b; }

.status-chip {
    display: inline-block;
    padding: 2px 10px; border-radius: 20px;
    font-size: 11px; font-weight: 600;
}
.status-aberto    { background:#2d2000; color:#f59e0b; border:1px solid #92400e; }
.status-encerrado { background:#0f2a1a; color:#22c55e; border:1px solid #166534; }

.attach-box {
    background: rgba(255,255,255,0.07);
    border-radius: 8px; padding: 8px 12px;
    margin-top: 6px; font-size: 12px;
}
.attach-box a { color: #818cf8; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Estado inicial
# ─────────────────────────────────────────────
defs = {
    "ini":             date.today() - timedelta(days=30),
    "fim":             date.today(),
    "protocolo_busca": "",
    "apenas_abertos":  True,
    "chat_selecionado":None,
}
for k, v in defs.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────
# Filtros
# ─────────────────────────────────────────────
st.markdown('<div class="filtro-box">', unsafe_allow_html=True)
st.markdown('<div class="sec-label">🔍 Filtros</div>', unsafe_allow_html=True)

fc1, fc2, fc3, fc4 = st.columns([2, 2, 3, 1])
with fc1:
    nova_ini = st.date_input("De", value=st.session_state["ini"],
                              format="DD/MM/YYYY", key="w_ini")
with fc2:
    nova_fim = st.date_input("Até", value=st.session_state["fim"],
                              format="DD/MM/YYYY", key="w_fim")
with fc3:
    prot_input = st.text_input(
        "Protocolo",
        value=st.session_state["protocolo_busca"],
        placeholder="Ex: 8162439  —  deixe vazio para listar todos",
        key="w_prot",
    )
with fc4:
    st.markdown("<br>", unsafe_allow_html=True)
    apenas_ab = st.checkbox("Só abertos",
                             value=st.session_state["apenas_abertos"],
                             key="w_ab")

fb1, fb2, fb3, _ = st.columns([1, 1, 1, 4])
with fb1:
    btn_filtrar = st.button("🔍 Filtrar", use_container_width=True, type="primary")
with fb2:
    btn_hoje    = st.button("📅 Hoje", use_container_width=True)
with fb3:
    btn_semana  = st.button("📆 Esta semana", use_container_width=True)

st.markdown('</div>', unsafe_allow_html=True)

if btn_hoje:
    st.session_state.update({"ini": date.today(), "fim": date.today()})
    st.session_state.pop("df_cache", None)
    st.rerun()
if btn_semana:
    seg = date.today() - timedelta(days=date.today().weekday())
    st.session_state.update({"ini": seg, "fim": date.today()})
    st.session_state.pop("df_cache", None)
    st.rerun()
if btn_filtrar:
    st.session_state.update({
        "ini":             nova_ini,
        "fim":             nova_fim,
        "protocolo_busca": prot_input.strip(),
        "apenas_abertos":  apenas_ab,
        "chat_selecionado":None,
    })
    st.session_state.pop("df_cache", None)
    st.rerun()

ini_usada  = st.session_state["ini"]
fim_usada  = st.session_state["fim"]
prot_usada = st.session_state["protocolo_busca"]
ab_flag    = st.session_state["apenas_abertos"]

# Debug
with st.expander("🔧 Diagnóstico da API", expanded=False):
    dbg = st.checkbox("Ativar debug", value=False, key="debug_mode")
    if st.session_state.get("debug_mode"):
        st.session_state.pop("df_cache", None)
dbg = st.session_state.get("debug_mode", False)

# ─────────────────────────────────────────────
# Busca
# ─────────────────────────────────────────────
cache_key = f"{ini_usada}_{fim_usada}_{prot_usada}_{ab_flag}"
if st.session_state.get("_ck") != cache_key or "df_cache" not in st.session_state:
    with st.spinner("🔄 Consultando API Gove..."):
        df, chats = buscar_atendimentos(
            data_ini=None if prot_usada else ini_usada.strftime("%d/%m/%Y"),
            data_fim=None if prot_usada else fim_usada.strftime("%d/%m/%Y"),
            protocolo=prot_usada or None,
            apenas_abertos=ab_flag,
            debug=dbg,
        )
    st.session_state["df_cache"]  = df
    st.session_state["raw_chats"] = chats
    st.session_state["_ck"]       = cache_key
else:
    df    = st.session_state["df_cache"]
    chats = st.session_state["raw_chats"]

total = len(df)

# ─────────────────────────────────────────────
# KPIs
# ─────────────────────────────────────────────
def _nu(df, col):
    if df.empty or col not in df.columns: return 0
    return int(df[col].astype(str).replace({"—":""}).nunique())

def _cv(df, col):
    if df.empty or col not in df.columns: return 0
    return int(df[col].astype(str).isin({"—","-","","None","nan"}).sum())

sem_at   = _cv(df, "Atendente")
com_at   = total - sem_at
pct_com  = f"{com_at/total*100:.0f}%" if total else "—"
n_setores= _nu(df, "Setor")

k1, k2, k3, k4 = st.columns(4)
for col_k, lbl, val, cor, sub in [
    (k1,"Atendimentos", f"{total:,}",    "#f59e0b",
         f"{'abertos · ' if ab_flag else ''}{ini_usada.strftime('%d/%m')}→{fim_usada.strftime('%d/%m/%Y')}"),
    (k2,"Setores",      f"{n_setores:,}","#6366f1","com pendências"),
    (k3,"Sem Atendente",f"{sem_at:,}",   "#ef4444","aguardando atribuição"),
    (k4,"Com Atendente",pct_com,          "#22c55e","dos atendimentos"),
]:
    with col_k:
        st.markdown(f"""<div class="kpi">
            <div class="kpi-lbl">{lbl}</div>
            <div class="kpi-val" style="color:{cor}">{val}</div>
            <div class="kpi-sub">{sub}</div>
        </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Barra: live + integrar
# ─────────────────────────────────────────────
ci, cb = st.columns([5, 1])
with ci:
    st.markdown(
        f"**{total:,}** atendimento(s) &nbsp;·&nbsp;"
        f"<span class='live-pill'><span class='dot'></span>AO VIVO</span>"
        f"&nbsp;<span style='font-size:12px;color:#64748b'>{agora.strftime('%d/%m/%Y %H:%M:%S')}</span>"
        f"&nbsp;·&nbsp;<span style='font-size:12px;color:#94a3b8'>💬 Clique em uma linha para ver a conversa</span>",
        unsafe_allow_html=True,
    )
with cb:
    btn_integrar = st.button(
        "⬆️ Integrar ao Supabase",
        use_container_width=True, type="primary",
        disabled=(total == 0),
    )

if btn_integrar and chats:
    with st.spinner("Integrando ao Supabase..."):
        res = integrar_tudo(chats)
    if res.get("ok"):
        st.success(
            f"✅ Integração concluída! "
            f"Atendentes: **{res['atendentes']['count']}** · "
            f"Setores: **{res['setores']['count']}** · "
            f"Atendimentos: **{res['atendimentos']['count']}**"
        )
    else:
        for ent, r in res.items():
            if isinstance(r, dict) and not r.get("ok"):
                st.error(f"❌ {ent}: {r.get('error','—')}")

st.markdown("")

# ─────────────────────────────────────────────
# Tabela com seleção de linha
# ─────────────────────────────────────────────
if df.empty:
    st.markdown("""
    <div style="text-align:center;padding:50px;color:#64748b">
        <div style="font-size:42px;margin-bottom:10px">📭</div>
        <div>Nenhum atendimento encontrado. Ajuste os filtros e clique em Filtrar.</div>
    </div>
    """, unsafe_allow_html=True)
else:
    busca = st.text_input("busca", placeholder="🔍 Buscar na tabela...",
                           label_visibility="collapsed")
    df_exib = df.copy()
    if busca.strip():
        mask = pd.Series(False, index=df_exib.index)
        for c in df_exib.columns:
            mask |= df_exib[c].astype(str).str.lower().str.contains(
                busca.strip().lower(), na=False)
        df_exib = df_exib[mask]

    evento = st.dataframe(
        df_exib,
        use_container_width=True,
        height=min(60 + len(df_exib) * 36, 560),
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Protocolo":    st.column_config.TextColumn("Protocolo",    width="small"),
            "Contribuinte": st.column_config.TextColumn("Contribuinte", width="small"),
            "Atendente":    st.column_config.TextColumn("Atendente",    width="medium"),
            "Setor":        st.column_config.TextColumn("Setor",        width="large"),
            "Sigla":        st.column_config.TextColumn("Sigla",        width="small"),
            "Status":       st.column_config.TextColumn("Status",       width="small"),
            "Aberto em":    st.column_config.TextColumn("Aberto em",    width="small"),
            "Encerrado em": st.column_config.TextColumn("Encerrado em", width="small"),
        },
    )

    # ── Detecta seleção e abre dialog ────────────────────────────
    linhas = evento.selection.rows if evento.selection else []
    if linhas:
        idx   = linhas[0]
        linha = df_exib.iloc[idx]
        chat_id = str(linha["Protocolo"])

        # Encontra o chat parsed correspondente
        chat_raw = next((c for c in chats if str(c["id"]) == chat_id), {})
        recipient_contribuinte = chat_raw.get("recipient")

        # Guarda no state para o dialog
        if st.session_state.get("chat_selecionado") != chat_id:
            st.session_state["chat_selecionado"] = chat_id
            st.session_state["chat_raw"]         = chat_raw
            st.session_state["chat_msgs"]        = None  # força reload

    st.markdown("")
    csv = df_exib.to_csv(index=False, sep=";", encoding="utf-8-sig")
    st.download_button("⬇️ Exportar CSV", data=csv,
                        file_name=f"atendimentos_{date.today().strftime('%d%m%Y')}.csv",
                        mime="text/csv")

# ─────────────────────────────────────────────
# Dialog: Conversa
# ─────────────────────────────────────────────
chat_id  = st.session_state.get("chat_selecionado")
chat_raw = st.session_state.get("chat_raw", {})

if chat_id:
    @st.dialog(f"💬 Conversa — Protocolo {chat_id}", width="large")
    def dialog_conversa():
        recipient = chat_raw.get("recipient", "—")
        atendente = chat_raw.get("agent_name") or "Não atribuído"
        setor     = chat_raw.get("sector_name") or "—"
        sigla     = chat_raw.get("sector_acronym") or ""
        status    = chat_raw.get("_status", "—")
        aberto_em = chat_raw.get("_started_fmt", "—")
        enc_em    = chat_raw.get("_finished_fmt", "—")

        chip_cls  = "status-aberto" if status == "Aberto" else "status-encerrado"
        setor_txt = f"{setor} ({sigla})" if sigla else setor

        # Info bar
        st.markdown(f"""
        <div class="chat-info-bar">
            <span>📱 <b>{recipient}</b></span>
            <span>🎧 <b>{atendente}</b></span>
            <span>🏢 {setor_txt}</span>
            <span>📅 {aberto_em}</span>
            {'<span>🏁 ' + enc_em + '</span>' if status == "Encerrado" else ''}
            <span><span class="status-chip {chip_cls}">{status}</span></span>
        </div>
        """, unsafe_allow_html=True)

        # Carrega mensagens (1x por chat)
        if st.session_state.get("chat_msgs") is None:
            with st.spinner("Carregando conversa..."):
                msgs = buscar_mensagens(chat_id, recipient_contribuinte=recipient)
                st.session_state["chat_msgs"] = msgs
        else:
            msgs = st.session_state["chat_msgs"]

        if not msgs:
            st.markdown("""
            <div style="text-align:center;padding:40px;color:#64748b">
                <div style="font-size:36px;margin-bottom:8px">💬</div>
                <div>Nenhuma mensagem encontrada neste atendimento.</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("🔄 Tentar novamente"):
                st.session_state["chat_msgs"] = None
                st.rerun()
            return

        # ── Renderiza as mensagens ────────────────────────────────
        st.markdown(
            f"<div style='font-size:12px;color:#64748b;margin-bottom:12px'>"
            f"{len(msgs)} mensagem(ns) · cronológica (mais antiga → mais recente)"
            f"</div>",
            unsafe_allow_html=True
        )

        chat_html = ""
        for m in msgs:
            lado      = m["lado"]       # "sistema" ou "contribuinte"
            texto     = m["body"] or ""
            hora      = m["sent_at_fmt"] or ""
            status_m  = m.get("send_status_confirmation") or m.get("send_status") or ""
            attach    = m.get("attachment")

            # Label identificador
            if lado == "sistema":
                label_html = f'<div class="msg-label msg-label-sistema">Prefeitura ↗</div>'
                row_cls    = "msg-row-sistema"
                bubble_cls = "msg-bubble msg-sistema"
                status_icon = " ✓✓" if status_m == "received" else " ✓" if status_m == "transmitted" else ""
                meta_html  = f'<div class="msg-meta">{hora}{status_icon}</div>'
            else:
                label_html = f'<div class="msg-label msg-label-contribuinte">Cidadão ↙</div>'
                row_cls    = "msg-row-contribuinte"
                bubble_cls = "msg-bubble msg-contribuinte"
                meta_html  = f'<div class="msg-meta">{hora}</div>'

            # Conteúdo: texto + anexo
            corpo = texto.replace("<","&lt;").replace(">","&gt;")

            if attach:
                if isinstance(attach, dict):
                    a_url  = attach.get("url","")
                    a_nome = attach.get("name") or attach.get("filename") or "Anexo"
                    a_tipo = attach.get("mime_type") or attach.get("type","")
                    is_img = a_tipo.startswith("image") if a_tipo else False
                    if is_img and a_url:
                        attach_html = f'<div class="attach-box">🖼️ <a href="{a_url}" target="_blank">{a_nome}</a></div>'
                    elif a_url:
                        attach_html = f'<div class="attach-box">📎 <a href="{a_url}" target="_blank">{a_nome}</a></div>'
                    else:
                        attach_html = f'<div class="attach-box">📎 {a_nome}</div>'
                else:
                    attach_html = f'<div class="attach-box">📎 {attach}</div>'
            else:
                attach_html = ""

            chat_html += f"""
            <div class="msg-row {row_cls}">
                <div>
                    {label_html}
                    <div class="{bubble_cls}">
                        {corpo}
                        {attach_html}
                        {meta_html}
                    </div>
                </div>
            </div>
            """

        st.markdown(chat_html, unsafe_allow_html=True)

        # Rodapé do dialog
        st.markdown("---")
        col_r, col_f = st.columns([3, 1])
        with col_r:
            st.caption(f"📋 Protocolo {chat_id} · Canal: {msgs[0].get('channel','—') if msgs else '—'}")
        with col_f:
            if st.button("✖ Fechar", use_container_width=True):
                st.session_state["chat_selecionado"] = None
                st.rerun()

    dialog_conversa()

# ─────────────────────────────────────────────
# Rodapé
# ─────────────────────────────────────────────
st.markdown("---")
st.caption(
    f"🕒 {agora.strftime('%d/%m/%Y %H:%M:%S')} · "
    "Cache 5 min · API Gove Digital · Prefeitura de Rio Verde"
)
