"""
pages/2_🔴_Abertos.py
Atendimentos em aberto — tempo real via API Gove.
Salva snapshots no Supabase para histórico.
Requer login.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, date, time, timedelta
import time as time_module

from supabase_auth import require_login, get_user, logout
from gove_api import listar_atendimentos, status_api
from supabase_logs import salvar_snapshot, buscar_historico

# ── Guard ─────────────────────────────────────────────────────────
require_login()

# ─────────────────────────────────────────────
# Configuração
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Atendimentos em Aberto",
    page_icon="🔴",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────
FERIADOS = {date(2026, 4, 2), date(2026, 4, 20), date(2026, 4, 21)}
MIN_DIA  = 570  # 08:00–17:30

FAIXAS = [
    "⚡ Menos de 5 min",
    "🟢 5 a 30 min",
    "🟡 30 min a 1h",
    "🟠 1h a 4h",
    "🔴 4h a 8h",
    "🔵 8h a 24h (1 dia útil)",
    "⛔ Acima de 1 dia útil",
]
COR_FAIXA = {
    "⚡ Menos de 5 min":        "#6366f1",
    "🟢 5 a 30 min":            "#22c55e",
    "🟡 30 min a 1h":           "#f59e0b",
    "🟠 1h a 4h":               "#fb923c",
    "🔴 4h a 8h":               "#ef4444",
    "🔵 8h a 24h (1 dia útil)": "#3b82f6",
    "⛔ Acima de 1 dia útil":   "#7c3aed",
}
CSS_FAIXA = {
    "⛔ Acima de 1 dia útil":   "background-color:#2d1229;color:#c084fc",
    "🔵 8h a 24h (1 dia útil)": "background-color:#172035;color:#60a5fa",
    "🔴 4h a 8h":               "background-color:#2d1515;color:#f87171",
    "🟠 1h a 4h":               "background-color:#2d1f0a;color:#fb923c",
    "🟡 30 min a 1h":           "background-color:#2a2007;color:#fbbf24",
    "🟢 5 a 30 min":            "background-color:#0f2a1a;color:#4ade80",
    "⚡ Menos de 5 min":        "background-color:#1a1a2e;color:#818cf8",
}

# ─────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background-color: #0f1117; }
    section[data-testid="stSidebar"] { background-color: #1a1d27; }
    .kpi-card {
        background: linear-gradient(135deg,#1e2130,#252a3d);
        border:1px solid #2e3450; border-radius:12px;
        padding:18px 20px; text-align:center;
        box-shadow:0 4px 15px rgba(0,0,0,0.3);
    }
    .kpi-label { font-size:11px; color:#8b92a5; text-transform:uppercase;
                 letter-spacing:1px; margin-bottom:5px; }
    .kpi-value { font-size:28px; font-weight:700; line-height:1.1; }
    .kpi-sub   { font-size:11px; color:#5c6880; margin-top:3px; }
    .live-pill {
        display:inline-flex; align-items:center; gap:7px;
        background:#0d1f0d; border:1px solid #166534;
        border-radius:20px; padding:5px 14px;
        font-size:12px; font-weight:600; color:#4ade80;
    }
    .dot { width:8px; height:8px; border-radius:50%;
           background:#22c55e; animation:pulse 2s infinite; }
    @keyframes pulse {
        0%,100%{opacity:1;transform:scale(1)}
        50%{opacity:.4;transform:scale(1.4)}
    }
    hr { border-color:#2e3450; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def is_util(d: date) -> bool:
    return d.weekday() < 5 and d not in FERIADOS

def min_uteis(ab: datetime, enc: datetime) -> float | None:
    if pd.isna(ab) or pd.isna(enc): return None
    if enc <= ab: return 0.0
    total, cur = 0.0, ab
    while cur.date() <= enc.date():
        da = cur.date()
        if is_util(da):
            ini = max(cur, datetime.combine(da, time(8, 0)))
            fim = min(enc, datetime.combine(da, time(17, 30)))
            if fim > ini:
                total += (fim - ini).total_seconds() / 60
        cur = datetime.combine(da + timedelta(days=1), time(0, 0))
    return round(total, 2)

def faixa(m) -> str:
    if m is None or pd.isna(m): return "⚡ Menos de 5 min"
    m = float(m)
    if m < 5:    return "⚡ Menos de 5 min"
    if m < 30:   return "🟢 5 a 30 min"
    if m < 60:   return "🟡 30 min a 1h"
    if m < 240:  return "🟠 1h a 4h"
    if m < 480:  return "🔴 4h a 8h"
    if m < 570:  return "🔵 8h a 24h (1 dia útil)"
    return "⛔ Acima de 1 dia útil"

def fmt(m) -> str:
    if m is None or pd.isna(m): return "—"
    m = float(m)
    h, mn = int(m // 60), int(m % 60)
    if m / MIN_DIA >= 1: return f"{m/MIN_DIA:.1f}d úteis"
    return f"{h}h {mn:02d}min" if h else f"{mn}min"

def dark(fig, h=300):
    fig.update_layout(
        paper_bgcolor="#1a1d27", plot_bgcolor="#1a1d27",
        font=dict(color="#c8d0e0", family="Inter, sans-serif"),
        xaxis=dict(gridcolor="#2e3450", linecolor="#2e3450", tickfont=dict(size=11)),
        yaxis=dict(gridcolor="#2e3450", linecolor="#2e3450", tickfont=dict(size=11)),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
        margin=dict(l=10, r=10, t=35, b=10), height=h,
    )
    return fig

# ─────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────
u    = get_user()
nome = u.get("nome", "Usuário")

with st.sidebar:
    st.markdown(f"""
    <div style="background:#1e2130;border:1px solid #2e3450;
                border-radius:10px;padding:11px 14px;margin-bottom:12px">
        <div style="font-size:13px;font-weight:600;color:#e2e8f0">👤 {nome}</div>
        <div style="font-size:11px;color:#64748b">{u.get("email","")}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### ⚙️ Filtros")

    faixas_sel = st.multiselect("⏱️ Faixa de Tempo", FAIXAS, default=[],
                                placeholder="Todas as faixas")

    busca_txt = st.text_input("🔍 Buscar (protocolo / setor / atendente)", value="")

    st.markdown("---")
    st.markdown("#### 📖 Histórico Supabase")
    ver_historico = st.checkbox("Ver histórico salvo", value=False)
    if ver_historico:
        hist_ini = st.date_input("De", value=date.today() - timedelta(days=7))
        hist_fim = st.date_input("Até", value=date.today())

    st.markdown("---")
    if st.button("📊 Dashboard Principal", use_container_width=True):
        st.switch_page("pages/1_📊_Dashboard.py")
    if st.button("🚪 Sair", use_container_width=True):
        logout()
        st.switch_page("login.py")

# ─────────────────────────────────────────────
# Cabeçalho
# ─────────────────────────────────────────────
agora = datetime.now()
ch1, ch2 = st.columns([4, 1])
with ch1:
    st.markdown("# 🔴 Atendimentos em Aberto")
    st.caption("Dados em tempo real via **API Gove** · Horas úteis 08:00–17:30 · Seg–Sex")
with ch2:
    api_cor  = "#22c55e" if status_api() else "#ef4444"
    api_txt  = "API Online" if status_api() else "API Offline"
    st.markdown(f"""
    <div style="margin-top:16px;text-align:right">
        <div class="live-pill"><div class="dot"></div>AO VIVO</div>
        <div style="font-size:11px;color:{api_cor};margin-top:4px">● {api_txt}</div>
        <div style="font-size:11px;color:#64748b">{agora.strftime('%d/%m/%Y %H:%M:%S')}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# ─────────────────────────────────────────────
# Histórico Supabase (opcional)
# ─────────────────────────────────────────────
if ver_historico:
    with st.expander("📖 Histórico salvo no Supabase", expanded=True):
        with st.spinner("Buscando histórico..."):
            df_hist = buscar_historico(
                data_ini=hist_ini.isoformat(),
                data_fim=hist_fim.isoformat(),
            )
        if df_hist.empty:
            st.info("Nenhum registro encontrado no período.")
        else:
            st.dataframe(df_hist, use_container_width=True, height=300)
            st.caption(f"{len(df_hist):,} registros encontrados")
    st.markdown("---")

# ─────────────────────────────────────────────
# Busca dados em tempo real (API Gove)
# ─────────────────────────────────────────────
with st.spinner("🔄 Consultando API Gove..."):
    ini_api = (date.today() - timedelta(days=90)).strftime("%d/%m/%Y")
    fim_api = date.today().strftime("%d/%m/%Y")
    df_api  = listar_atendimentos(
        started_at_initial=ini_api,
        started_at_final=fim_api,
        order_direction="desc",
    )

if df_api.empty:
    st.warning("⚠️ Nenhum dado retornado pela API Gove. Verifique token e conexão.")
    st.stop()

# ─────────────────────────────────────────────
# Filtra apenas ABERTOS (sem finished_at)
# ─────────────────────────────────────────────
col_fim = next(
    (c for c in ["finished_at","encerrado_em","closed_at","ended_at"]
     if c in df_api.columns), None
)
df = df_api[df_api[col_fim].isna()].copy() if col_fim else df_api.copy()

# ─────────────────────────────────────────────
# Identifica colunas dinâmicas da API
# ─────────────────────────────────────────────
col_ini   = next((c for c in ["started_at","created_at","aberto_em","opened_at"]   if c in df.columns), None)
col_setor = next((c for c in ["sector","setor","sector_name","department"]          if c in df.columns), None)
col_agent = next((c for c in ["agent","agent_name","atendente","assigned_to"]       if c in df.columns), None)
col_prot  = next((c for c in ["id","protocolo","protocol","chat_id"]                if c in df.columns), None)

# ─────────────────────────────────────────────
# Calcula horas úteis em aberto
# ─────────────────────────────────────────────
if col_ini:
    df[col_ini] = pd.to_datetime(df[col_ini], errors="coerce")
    df["_min"]  = df[col_ini].apply(lambda ab: min_uteis(ab, agora) if pd.notna(ab) else None)
else:
    df["_min"]  = None

df["Faixa"]           = df["_min"].apply(faixa)
df["Tempo em Aberto"] = df["_min"].apply(fmt)
df["Aberto em"]       = df[col_ini].dt.strftime("%d/%m/%Y %H:%M") if col_ini else "—"

# ─────────────────────────────────────────────
# Aplica filtros
# ─────────────────────────────────────────────
if faixas_sel:
    df = df[df["Faixa"].isin(faixas_sel)]

if busca_txt.strip():
    txt = busca_txt.strip().lower()
    mask = pd.Series(False, index=df.index)
    for c in [col_prot, col_setor, col_agent]:
        if c and c in df.columns:
            mask |= df[c].astype(str).str.lower().str.contains(txt, na=False)
    df = df[mask]

# ─────────────────────────────────────────────
# Salva snapshot no Supabase (em background)
# ─────────────────────────────────────────────
if not df.empty:
    salvar_snapshot(df, fonte="api_gove")

# ─────────────────────────────────────────────
# KPIs
# ─────────────────────────────────────────────
total    = len(df)
criticos = len(df[df["Faixa"].isin(["🔴 4h a 8h","🔵 8h a 24h (1 dia útil)","⛔ Acima de 1 dia útil"])])
vencidos = len(df[df["Faixa"] == "⛔ Acima de 1 dia útil"])
tma      = fmt(df["_min"].dropna().mean()) if total > 0 else "—"
pct_crit = f"{criticos/total*100:.1f}%" if total > 0 else "—"

k1, k2, k3, k4, k5 = st.columns(5)
kpis = [
    (k1, "Em Aberto",          f"{total:,}",   "#f59e0b", "total pendente"),
    (k2, "🔴 Críticos",        f"{criticos:,}","#ef4444",  "> 4h úteis"),
    (k3, "⛔ Vencidos",        f"{vencidos:,}","#7c3aed",  "> 1 dia útil"),
    (k4, "% Crítico/Total",    pct_crit,        "#fb923c",  "dos atendimentos"),
    (k5, "TMA em Aberto",      tma,             "#f97316",  "horas úteis"),
]
for col, lbl, val, cor, sub in kpis:
    with col:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">{lbl}</div>
            <div class="kpi-value" style="color:{cor}">{val}</div>
            <div class="kpi-sub">{sub}</div>
        </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Gráficos — linha 1
# ─────────────────────────────────────────────
cg1, cg2 = st.columns([3, 2])

with cg1:
    st.markdown("#### 📊 Distribuição por Faixa de Tempo Útil")
    fc = (df["Faixa"].value_counts()
          .reindex([f for f in FAIXAS if f in df["Faixa"].unique()])
          .fillna(0).reset_index())
    fc.columns = ["Faixa","Qtd"]
    fc["Cor"] = fc["Faixa"].map(COR_FAIXA)
    tot_fc = fc["Qtd"].sum()
    fc["Label"] = fc.apply(
        lambda r: f"{int(r.Qtd):,}  ({r.Qtd/tot_fc*100:.1f}%)" if tot_fc else str(int(r.Qtd)),
        axis=1)

    fig_f = go.Figure(go.Bar(
        x=fc["Faixa"], y=fc["Qtd"],
        marker_color=fc["Cor"],
        text=fc["Label"], textposition="outside",
        textfont=dict(size=11, color="#c8d0e0"),
    ))
    dark(fig_f, 320)
    fig_f.update_layout(xaxis_title="", yaxis_title="Qtd",
                         xaxis=dict(tickfont=dict(size=10)))
    st.plotly_chart(fig_f, use_container_width=True)

with cg2:
    st.markdown("#### 🏛️ Abertos por Setor (Top 10)")
    if col_setor and col_setor in df.columns:
        top = df[col_setor].value_counts().head(10).reset_index()
        top.columns = ["Setor","Qtd"]
        top = top.sort_values("Qtd", ascending=True)
        top["Setor_c"] = top["Setor"].apply(lambda x: str(x)[:28]+"…" if len(str(x))>28 else x)

        fig_s = go.Figure(go.Bar(
            x=top["Qtd"], y=top["Setor_c"], orientation="h",
            marker_color="#6366f1",
            text=top["Qtd"], textposition="outside",
            textfont=dict(size=11, color="#c8d0e0"),
        ))
        dark(fig_s, 320)
        fig_s.update_layout(xaxis_title="", yaxis_title="",
                             yaxis=dict(tickfont=dict(size=10)))
        st.plotly_chart(fig_s, use_container_width=True)
    else:
        st.info("Coluna de setor não encontrada no retorno da API.")

# ─────────────────────────────────────────────
# Gráfico — heatmap faixa × setor
# ─────────────────────────────────────────────
if col_setor and col_setor in df.columns and not df.empty:
    st.markdown("#### 🗂️ Faixa de Tempo × Setor")
    piv = df.groupby([col_setor, "Faixa"]).size().unstack(fill_value=0)
    cols_p = [f for f in FAIXAS if f in piv.columns]
    if cols_p:
        piv = piv[cols_p]
        piv["Total"] = piv.sum(axis=1)
        piv = piv.sort_values("Total", ascending=False).head(15)
        fig_h = go.Figure(go.Heatmap(
            z=piv[cols_p].values,
            x=[c.split(" ",1)[-1] if " " in c else c for c in cols_p],
            y=piv.index.tolist(),
            colorscale="YlOrRd",
            text=piv[cols_p].values,
            texttemplate="%{text}",
            textfont=dict(size=10),
            hovertemplate="<b>%{y}</b><br>%{x}: %{z}<extra></extra>",
            showscale=False,
        ))
        dark(fig_h, max(300, 55 + len(piv)*32))
        fig_h.update_layout(
            xaxis=dict(tickfont=dict(size=9), side="bottom"),
            yaxis=dict(tickfont=dict(size=9), autorange="reversed"),
            margin=dict(l=10, r=10, t=20, b=60),
        )
        st.plotly_chart(fig_h, use_container_width=True)

# ─────────────────────────────────────────────
# Tabela — Top 50 mais antigos
# ─────────────────────────────────────────────
st.markdown("---")
st.markdown(f"#### 📋 Atendimentos em Aberto — {total:,} encontrados")

# Monta colunas para exibição
cols_base = [col_prot, col_setor, col_agent, "Aberto em", "Tempo em Aberto", "Faixa"]
cols_tab  = [c for c in cols_base if c and c in df.columns]

# Remove duplicatas mantendo a ordem
seen, cols_tab = set(), [c for c in cols_tab if not (c in seen or seen.add(c))]

df_tab = (df.sort_values("_min", ascending=False)
          .head(50)[cols_tab])

# Renomeia para exibição amigável
rename = {}
if col_prot:  rename[col_prot]  = "Protocolo"
if col_setor: rename[col_setor] = "Setor"
if col_agent: rename[col_agent] = "Atendente"
df_tab = df_tab.rename(columns=rename)

try:
    styled = df_tab.style.map(lambda v: CSS_FAIXA.get(str(v),""), subset=["Faixa"])
except AttributeError:
    styled = df_tab.style.applymap(lambda v: CSS_FAIXA.get(str(v),""), subset=["Faixa"])

st.dataframe(styled, use_container_width=True, height=min(60+len(df_tab)*38, 540))

# ─────────────────────────────────────────────
# Rodapé + Auto-refresh 5 min
# ─────────────────────────────────────────────
st.markdown("---")
rf1, rf2 = st.columns(2)
with rf1:
    st.caption(f"🕒 Atualizado em: **{agora.strftime('%d/%m/%Y %H:%M:%S')}** · próximo em 5 min")
with rf2:
    st.caption("⏱️ Horas úteis: 08:00–17:30 · Seg–Sex · Feriados 02/04, 20/04, 21/04 excluídos")

time_module.sleep(300)
st.rerun()
