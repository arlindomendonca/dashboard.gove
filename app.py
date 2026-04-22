import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, time, timedelta
import time as time_module

# ─────────────────────────────────────────────
# Configuração da Página
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Dashboard de Atendimentos",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .stApp { background-color: #0f1117; }
    section[data-testid="stSidebar"] { background-color: #1a1d27; }
    .kpi-card {
        background: linear-gradient(135deg, #1e2130, #252a3d);
        border: 1px solid #2e3450; border-radius: 12px;
        padding: 20px 24px; text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    .kpi-label {
        font-size: 13px; color: #8b92a5;
        text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px;
    }
    .kpi-value { font-size: 32px; font-weight: 700; color: #ffffff; line-height: 1.1; }
    .kpi-sub   { font-size: 12px; color: #5c6880; margin-top: 4px; }
    .kpi-badge { font-size: 11px; color: #94a3b8; margin-top: 6px; font-style: italic; }
    .kpi-delta-pos { color: #22c55e; font-size: 13px; margin-top: 4px; }
    .kpi-delta-neg { color: #ef4444; font-size: 13px; margin-top: 4px; }
    .main-title { font-size: 28px; font-weight: 800; color: #e2e8f0; margin-bottom: 4px; }
    .main-subtitle { font-size: 14px; color: #64748b; margin-bottom: 28px; }
    .section-title {
        font-size: 13px; font-weight: 600; color: #94a3b8;
        text-transform: uppercase; letter-spacing: 0.8px; margin: 16px 0 6px 0;
    }
    .info-box {
        background: #1e2130; border-left: 3px solid #3b82f6;
        border-radius: 6px; padding: 10px 14px;
        font-size: 12px; color: #94a3b8; margin-bottom: 12px;
    }
    hr { border-color: #2e3450; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────
FAIXAS_ORDEM = [
    "⚡ Menos de 5 min",
    "🟢 5 a 30 min",
    "🟡 30 min a 1h",
    "🟠 1h a 4h",
    "🔴 4h a 8h",
    "🔵 8h a 24h (1 dia útil)",
    "⛔ Acima de 1 dia útil",
    "Sem registro",
    "N/A",
]

FAIXA_COLORS = {
    "⚡ Menos de 5 min":        "#6366f1",
    "🟢 5 a 30 min":            "#22c55e",
    "🟡 30 min a 1h":           "#f59e0b",
    "🟠 1h a 4h":               "#fb923c",
    "🔴 4h a 8h":               "#ef4444",
    "🔵 8h a 24h (1 dia útil)": "#3b82f6",
    "⛔ Acima de 1 dia útil":   "#7c3aed",
    "Sem registro":             "#6b7280",
    "N/A":                      "#374151",
}

FERIADOS = {
    date(2026, 4, 2),
    date(2026, 4, 20),
    date(2026, 4, 21),
}

MINUTOS_DIA_UTIL = 570  # 08:00 às 17:30

# ─────────────────────────────────────────────
# Helpers de horas úteis (usados apenas para KPI em tempo real)
# ─────────────────────────────────────────────
def is_dia_util(d: date) -> bool:
    return d.weekday() < 5 and d not in FERIADOS

def minutos_uteis(abertura: datetime, encerramento: datetime):
    if pd.isna(abertura) or pd.isna(encerramento):
        return None
    if encerramento <= abertura:
        return 0.0
    total = 0.0
    cursor = abertura
    while cursor.date() <= encerramento.date():
        da = cursor.date()
        if is_dia_util(da):
            ini = max(cursor, datetime.combine(da, time(8, 0)))
            fim = min(encerramento, datetime.combine(da, time(17, 30)))
            if fim > ini:
                total += (fim - ini).total_seconds() / 60
        cursor = datetime.combine(da + timedelta(days=1), time(0, 0))
    return round(total, 2)

def parse_tempo_util(val):
    """Converte 'H:MM:SS' da coluna Tempo Útil (HH:MM) para minutos."""
    if pd.isna(val) or str(val).strip() == '':
        return None
    try:
        p = str(val).strip().split(':')
        if len(p) == 3:
            return int(p[0]) * 60 + int(p[1]) + int(p[2]) / 60
    except Exception:
        return None

def fmt_minutos(min_val):
    if min_val is None or pd.isna(min_val):
        return "—"
    if min_val < 60:
        return f"{min_val:.0f} min"
    if min_val < MINUTOS_DIA_UTIL:
        return f"{min_val/60:.1f}h"
    dias = min_val / MINUTOS_DIA_UTIL
    return f"{dias:.1f} dia(s) útil(is)"

# ─────────────────────────────────────────────
# Carregamento de dados
# ─────────────────────────────────────────────
@st.cache_data(show_spinner="Carregando base de atendimentos...")
def load_data(filepath: str) -> pd.DataFrame:
    for enc in ("utf-8-sig", "latin1"):
        try:
            df = pd.read_csv(filepath, sep=";", encoding=enc,
                             low_memory=False, dtype=str)
            break
        except Exception:
            continue

    df.dropna(how="all", inplace=True)
    df.columns = df.columns.str.strip()

    for col in ["Aberto em", "Encerrado em"]:
        if col in df.columns:
            # Tenta formato BR primeiro; se maioria falhar, usa inferência automática
            parsed = pd.to_datetime(df[col], format="%d/%m/%Y %H:%M", errors="coerce")
            if parsed.isna().mean() > 0.5:
                parsed = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
            df[col] = parsed

    # Tempo útil em minutos (da coluna pré-calculada)
    if "Tempo Útil (HH:MM)" in df.columns:
        df["Tempo_util_min"] = df["Tempo Útil (HH:MM)"].apply(parse_tempo_util)
    else:
        df["Tempo_util_min"] = None

    for col in ["Status", "Atendente", "Setor", "Faixa de Tempo", "Departamento"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    return df


DATA_PATH = "base_atendimento_enriquecida.csv"
try:
    df_raw = load_data(DATA_PATH)
except FileNotFoundError:
    st.error(
        f"❌ Arquivo `{DATA_PATH}` não encontrado. "
        "Certifique-se de que ele está na mesma pasta que `app.py`."
    )
    st.stop()

# ─────────────────────────────────────────────
# Helper: tema escuro para gráficos Plotly
# ─────────────────────────────────────────────
FC = "#c8d0e0"   # cor padrão de texto nos gráficos

def dark(fig, height=320):
    fig.update_layout(
        paper_bgcolor="#1a1d27",
        plot_bgcolor="#1a1d27",
        font=dict(color=FC, family="Inter, sans-serif"),
        xaxis=dict(gridcolor="#2e3450", linecolor="#2e3450", tickfont=dict(size=11)),
        yaxis=dict(gridcolor="#2e3450", linecolor="#2e3450", tickfont=dict(size=11)),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=12)),
        margin=dict(l=10, r=10, t=40, b=10),
        height=height,
    )
    return fig

# ─────────────────────────────────────────────
# Sidebar – Filtros
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Filtros")

    st.markdown("""<div class="info-box">
        ⏱️ Horas úteis: <b>08:00 – 17:30</b><br>
        📅 Sáb/Dom e feriados excluídos<br>
        🚫 02/04 e 20/04 sem expediente
    </div>""", unsafe_allow_html=True)

    st.markdown("---")

    datas_validas = df_raw["Aberto em"].dropna()
    _fallback = date.today()
    min_date = datas_validas.min().date() if len(datas_validas) > 0 else _fallback
    max_date = datas_validas.max().date() if len(datas_validas) > 0 else _fallback
    if pd.isna(min_date): min_date = _fallback
    if pd.isna(max_date): max_date = _fallback

    # Filtros rápidos (via session_state)
    _ini_val = st.session_state.get("_date_ini", min_date)
    _fim_val = st.session_state.get("_date_fim", max_date)

    st.markdown('<div class="section-title">📅 Período de Abertura</div>', unsafe_allow_html=True)
    date_ini = st.date_input("De", value=_ini_val, min_value=min_date, max_value=max_date, key="date_ini_w")
    date_fim = st.date_input("Até", value=_fim_val, min_value=min_date, max_value=max_date, key="date_fim_w")
    st.markdown("---")

    CHATBOT_LABEL = "Chatbot / Inatividade"
    TI_LABEL      = "TI / Autenticação Digital"
    HIDDEN_LABELS = {CHATBOT_LABEL, TI_LABEL}

    st.markdown('<div class="section-title">⚡ Filtro Rápido</div>', unsafe_allow_html=True)
    col_fw1, col_fw2 = st.columns(2)
    with col_fw1:
        if st.button("📅 Esta semana", use_container_width=True):
            hoje_fw = date.today()
            seg = hoje_fw - timedelta(days=hoje_fw.weekday())
            dom = seg + timedelta(days=6)
            st.session_state["_date_ini"] = max(seg, df_raw["Aberto em"].dropna().min().date())
            st.session_state["_date_fim"] = min(dom, df_raw["Aberto em"].dropna().max().date())
    with col_fw2:
        if st.button("🗓️ Este mês", use_container_width=True):
            hoje_fw = date.today()
            inicio_mes = hoje_fw.replace(day=1)
            st.session_state["_date_ini"] = max(inicio_mes, df_raw["Aberto em"].dropna().min().date())
            st.session_state["_date_fim"] = df_raw["Aberto em"].dropna().max().date()
    st.markdown("---")

    ver_chatbot = st.checkbox("🤖 Ver Chatbot / Inatividade", value=False)
    ver_ti      = st.checkbox("💻 Ver TI / Autenticação Digital", value=False)
    st.markdown("---")

    hidden = set()
    if not ver_chatbot: hidden.add(CHATBOT_LABEL)
    if not ver_ti:      hidden.add(TI_LABEL)
    deptos_disp = sorted([d for d in df_raw["Departamento"].dropna().unique()
                          if d not in ("nan", "") and d not in hidden])
    st.markdown('<div class="section-title">🏛️ Departamento</div>', unsafe_allow_html=True)
    deptos_sel = st.multiselect("Departamento", options=deptos_disp, default=[],
                                placeholder="Todos os departamentos",
                                label_visibility="collapsed")
    st.markdown("---")

    setores_disp = sorted([s for s in df_raw["Setor"].dropna().unique()
                           if s not in ("nan", "", "-")])
    st.markdown('<div class="section-title">🏢 Setor</div>', unsafe_allow_html=True)
    setores_sel = st.multiselect("Setor", options=setores_disp, default=[],
                                 placeholder="Todos os setores",
                                 label_visibility="collapsed")
    st.markdown("---")

    status_disp = sorted([s for s in df_raw["Status"].dropna().unique()
                          if s not in ("nan", "")])
    st.markdown('<div class="section-title">🔖 Status</div>', unsafe_allow_html=True)
    status_sel = st.multiselect("Status", options=status_disp, default=[],
                                placeholder="Todos os status",
                                label_visibility="collapsed")
    st.markdown("---")

    faixas_disp = [f for f in FAIXAS_ORDEM if f in df_raw["Faixa de Tempo"].unique()]
    st.markdown('<div class="section-title">⏱️ Faixa de Tempo (horas úteis)</div>', unsafe_allow_html=True)
    faixas_sel = st.multiselect("Faixa", options=faixas_disp, default=[],
                                placeholder="Todas as faixas",
                                label_visibility="collapsed")
    st.markdown("---")
    st.caption(f"Base: **{len(df_raw):,}** registros")

# ─────────────────────────────────────────────
# Aplica Filtros
# ─────────────────────────────────────────────
df = df_raw.copy()
df = df[(df["Aberto em"].dt.date >= date_ini) & (df["Aberto em"].dt.date <= date_fim)]
# Exclui grupos ocultos conforme checkboxes
if not ver_chatbot:
    df = df[df["Departamento"] != "Chatbot / Inatividade"]
if not ver_ti:
    df = df[df["Departamento"] != "TI / Autenticação Digital"]
if deptos_sel:
    df = df[df["Departamento"].isin(deptos_sel)]
if setores_sel:
    df = df[df["Setor"].isin(setores_sel)]
if status_sel:
    df = df[df["Status"].isin(status_sel)]
# O filtro de Faixa de Tempo se aplica APENAS aos encerrados.
# Os abertos têm Faixa calculada em tempo real — não filtrar aqui.
if faixas_sel:
    mask_enc_faixa = (df["Status"].str.lower() == "encerrado") & (df["Faixa de Tempo"].isin(faixas_sel))
    mask_abertos   = df["Status"].str.lower() == "aberto"
    df = df[mask_enc_faixa | mask_abertos]


# ─────────────────────────────────────────────
# Cabeçalho
# ─────────────────────────────────────────────
st.markdown('<div class="main-title">📊 Dashboard de Atendimentos</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="main-subtitle">Período: {date_ini.strftime("%d/%m/%Y")} a '
    f'{date_fim.strftime("%d/%m/%Y")} &nbsp;|&nbsp; '
    f'Registros filtrados: <b>{len(df):,}</b> &nbsp;|&nbsp; '
    f'⏱️ TMA calculado em <b>horas úteis</b> (08:00–17:30, dias úteis)</div>',
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────
# ABAS PRINCIPAIS
# ─────────────────────────────────────────────
aba_enc, aba_ab = st.tabs(["✅ Encerrados", "🔴 Em Aberto"])

# ════════════════════════════════════════════════════════════════
# ABA 1 — ENCERRADOS
# ════════════════════════════════════════════════════════════════
with aba_enc:

    df_enc = df[df["Status"].str.lower() == "encerrado"].copy()

    # ── KPIs ──────────────────────────────────────────────────
    total     = len(df)
    pct_enc   = (len(df_enc) / total * 100) if total > 0 else 0
    tma_s     = df_enc["Tempo_util_min"].dropna()
    tma_str   = fmt_minutos(tma_s.mean()) if len(tma_s) > 0 else "—"
    hoje      = date.today()
    vol_hoje  = len(df[df["Aberto em"].dt.date == hoje])
    all_days  = pd.date_range(date_ini, date_fim)
    dias_uteis_periodo = max(sum(1 for d in all_days if is_dia_util(d.date())), 1)
    media_diaria = total / dias_uteis_periodo
    delta_pct    = ((vol_hoje - media_diaria) / media_diaria * 100) if media_diaria > 0 else 0
    dentro_sla   = len(df_enc[df_enc["Faixa de Tempo"].isin(
                        ["⚡ Menos de 5 min","🟢 5 a 30 min","🟡 30 min a 1h"])])
    pct_sla = (dentro_sla / len(df_enc) * 100) if len(df_enc) > 0 else 0

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Total Atendimentos</div>
            <div class="kpi-value">{total:,}</div>
            <div class="kpi-sub">no período</div>
        </div>""", unsafe_allow_html=True)
    with k2:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">% Encerrados</div>
            <div class="kpi-value">{pct_enc:.1f}%</div>
            <div class="kpi-sub">{len(df_enc):,} de {total:,}</div>
        </div>""", unsafe_allow_html=True)
    with k3:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">TMA (horas úteis)</div>
            <div class="kpi-value">{tma_str}</div>
            <div class="kpi-badge">08:00–17:30 · seg–sex</div>
        </div>""", unsafe_allow_html=True)
    with k4:
        dc = "kpi-delta-pos" if delta_pct >= 0 else "kpi-delta-neg"
        di = "▲" if delta_pct >= 0 else "▼"
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Hoje vs Média/Dia Útil</div>
            <div class="kpi-value">{vol_hoje:,}</div>
            <div class="{dc}">{di} {abs(delta_pct):.1f}% vs média ({media_diaria:.0f}/dia)</div>
        </div>""", unsafe_allow_html=True)
    with k5:
        sc = "kpi-delta-pos" if pct_sla >= 70 else "kpi-delta-neg"
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">SLA ≤ 1h (horas úteis)</div>
            <div class="kpi-value">{pct_sla:.1f}%</div>
            <div class="{sc}">{dentro_sla:,} atendimentos</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Gráficos ──────────────────────────────────────────────
    col_l, col_r = st.columns([3, 1])

    with col_l:
        st.markdown("#### 📈 Volume Temporal de Atendimentos (dias úteis)")
        vol_dia = (df.set_index("Aberto em").resample("D").size()
                   .reset_index(name="Quantidade"))
        vol_dia.columns = ["Data", "Quantidade"]
        vol_dia["Dia Útil"] = vol_dia["Data"].dt.date.apply(is_dia_util)
        if len(vol_dia) > 1:
            fig_line = px.line(vol_dia, x="Data", y="Quantidade", markers=True,
                               color_discrete_sequence=["#6366f1"])
            fig_line.update_traces(line=dict(width=2.5), marker=dict(size=6),
                                    fill="tozeroy", fillcolor="rgba(99,102,241,0.12)")
            for _, row in vol_dia[~vol_dia["Dia Útil"]].iterrows():
                fig_line.add_vrect(
                    x0=row["Data"] - pd.Timedelta(hours=12),
                    x1=row["Data"] + pd.Timedelta(hours=12),
                    fillcolor="rgba(239,68,68,0.08)", line_width=0,
                )
        else:
            vol_hora = (df.set_index("Aberto em").resample("h").size()
                        .reset_index(name="Quantidade"))
            vol_hora.columns = ["Hora", "Quantidade"]
            fig_line = px.bar(vol_hora, x="Hora", y="Quantidade",
                              color_discrete_sequence=["#6366f1"])
        dark(fig_line, 300)
        fig_line.update_layout(xaxis_title="", yaxis_title="Chamados")
        st.plotly_chart(fig_line, use_container_width=True)

    with col_r:
        st.markdown("#### 📊 % por Faixa de Tempo")
        _df_f2 = df_enc[~df_enc["Faixa de Tempo"].isin(["N/A","nan","Sem registro"])]
        if not _df_f2.empty:
            _fc2 = (
                _df_f2["Faixa de Tempo"].value_counts()
                .reindex([f for f in FAIXAS_ORDEM if f in _df_f2["Faixa de Tempo"].unique()])
                .fillna(0).reset_index()
            )
            _fc2.columns = ["Faixa","Qtd"]
            _total2 = _fc2["Qtd"].sum()
            _fc2["Pct"] = (_fc2["Qtd"] / _total2 * 100).round(1)
            _fc2["Cor"] = _fc2["Faixa"].map(FAIXA_COLORS)
            # Rosca percentual
            fig_pct = go.Figure(go.Pie(
                labels=_fc2["Faixa"],
                values=_fc2["Qtd"],
                hole=0.5,
                marker=dict(colors=_fc2["Cor"].tolist()),
                textinfo="percent",
                textfont=dict(size=11, color="#ffffff"),
                hovertemplate="<b>%{label}</b><br>%{value:,} atend. (%{percent})<extra></extra>",
            ))
            dark(fig_pct, 300)
            fig_pct.update_layout(
                showlegend=True,
                legend=dict(orientation="v", x=-0.1, y=0.5, font=dict(size=9)),
                margin=dict(l=0, r=0, t=40, b=0),
            )
            st.plotly_chart(fig_pct, use_container_width=True)
        else:
            st.info("Sem dados.")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### ⏱️ Distribuição por Faixa de Tempo Útil")
        df_faixa = df_enc[~df_enc["Faixa de Tempo"].isin(["N/A","nan","Sem registro"])]
        faixa_count = (
            df_faixa["Faixa de Tempo"].value_counts()
            .reindex([f for f in FAIXAS_ORDEM if f in df_faixa["Faixa de Tempo"].unique()])
            .fillna(0).reset_index()
        )
        faixa_count.columns = ["Faixa", "Qtd"]
        faixa_count["Cor"] = faixa_count["Faixa"].map(FAIXA_COLORS)
        fig_faixa = go.Figure(go.Bar(
            x=faixa_count["Faixa"], y=faixa_count["Qtd"],
            marker_color=faixa_count["Cor"],
            text=faixa_count["Qtd"].apply(lambda x: f"{int(x):,}"),
            textposition="outside", textfont=dict(size=11, color="#c8d0e0"),
        ))
        dark(fig_faixa, 360)
        fig_faixa.update_layout(xaxis_title="", yaxis_title="Atendimentos",
                                 xaxis=dict(tickfont=dict(size=10)))
        st.plotly_chart(fig_faixa, use_container_width=True)

    with col_b:
        st.markdown("#### 🏛️ Atendimentos por Departamento")
        df_dep = df_enc[~df_enc["Departamento"].isin(["nan",""])]
        depto_cnt = df_dep["Departamento"].value_counts().head(15).reset_index()
        depto_cnt.columns = ["Departamento","Qtd"]
        depto_cnt = depto_cnt.sort_values("Qtd", ascending=True)
        fig_dep = px.bar(depto_cnt, x="Qtd", y="Departamento", orientation="h",
                         color="Qtd", color_continuous_scale=["#1e3a5f","#3b82f6","#93c5fd"],
                         text="Qtd")
        fig_dep.update_traces(textposition="outside", textfont=dict(size=11, color="#c8d0e0"))
        dark(fig_dep, 360)
        fig_dep.update_layout(xaxis_title="Quantidade", yaxis_title="",
                              coloraxis_showscale=False, yaxis=dict(tickfont=dict(size=10)))
        st.plotly_chart(fig_dep, use_container_width=True)

    col_c, col_d = st.columns(2)
    with col_c:
        st.markdown("#### 🏢 Top 10 Setores Mais Demandados")
        top_set = (df[~df["Setor"].isin(["-","nan",""])]
                   ["Setor"].value_counts().head(10).reset_index())
        top_set.columns = ["Setor","Qtd"]
        top_set = top_set.sort_values("Qtd", ascending=True)
        top_set["Setor_curto"] = top_set["Setor"].apply(lambda x: x[:42]+"…" if len(x)>42 else x)
        fig_set = px.bar(top_set, x="Qtd", y="Setor_curto", orientation="h",
                         color="Qtd", color_continuous_scale=["#312e81","#6366f1","#a5b4fc"],
                         text="Qtd")
        fig_set.update_traces(textposition="outside", textfont=dict(size=11, color="#c8d0e0"))
        dark(fig_set, 380)
        fig_set.update_layout(xaxis_title="Quantidade", yaxis_title="",
                              coloraxis_showscale=False, yaxis=dict(tickfont=dict(size=10)))
        st.plotly_chart(fig_set, use_container_width=True)

    with col_d:
        st.markdown("#### 👤 Top 15 Atendentes")
        top_at = (df_enc[~df_enc["Atendente"].isin(["nan","NÃO ATRIBUIDO",""])]
                  ["Atendente"].value_counts().head(15).reset_index())
        top_at.columns = ["Atendente","Qtd"]
        top_at = top_at.sort_values("Qtd", ascending=False)
        fig_at = px.bar(top_at, x="Atendente", y="Qtd", color="Qtd",
                        color_continuous_scale=["#134e4a","#10b981","#6ee7b7"], text="Qtd")
        fig_at.update_traces(textposition="outside", textfont=dict(size=11, color="#c8d0e0"))
        dark(fig_at, 380)
        fig_at.update_layout(xaxis_title="", yaxis_title="Atendimentos",
                             coloraxis_showscale=False,
                             xaxis=dict(tickangle=-35, tickfont=dict(size=10)))
        st.plotly_chart(fig_at, use_container_width=True)

    st.markdown("#### ⏱️ TMA Médio por Departamento — horas úteis (08:00–17:30)")
    _df_tma_base = df_enc[~df_enc["Departamento"].isin(["nan","Chatbot / Inatividade","TI / Autenticação Digital"])]
    _tma_agg = _df_tma_base.groupby("Departamento").agg(
        TMA_min=("Tempo_util_min","mean"),
        Qtd=("Tempo_util_min","count")
    ).dropna().sort_values("TMA_min", ascending=False).head(12).reset_index()
    _tma_agg["Label"] = _tma_agg.apply(
        lambda r: f"{fmt_minutos(r['TMA_min'])}  ({int(r['Qtd']):,} atend.)", axis=1)
    df_tma = _tma_agg.sort_values("TMA_min", ascending=True)
    fig_tma = px.bar(df_tma, x="TMA_min", y="Departamento", orientation="h",
                     color="TMA_min", color_continuous_scale=["#7c2d12","#f97316","#fed7aa"],
                     text="Label")
    fig_tma.update_traces(textposition="outside", textfont=dict(size=11, color="#c8d0e0"))
    dark(fig_tma, 400)
    fig_tma.update_layout(xaxis_title="Minutos úteis", yaxis_title="",
                          coloraxis_showscale=False, yaxis=dict(tickfont=dict(size=10)))
    st.plotly_chart(fig_tma, use_container_width=True)

    st.markdown("#### 📋 Cruzamento: Faixa de Tempo Útil × Departamento")
    df_cross = df_enc[~df_enc["Faixa de Tempo"].isin(["N/A","nan","Sem registro"])]
    if not df_cross.empty:
        pivot = (df_cross.groupby(["Departamento","Faixa de Tempo"])
                 .size().unstack(fill_value=0))
        cols_ok = [f for f in FAIXAS_ORDEM if f in pivot.columns]
        pivot = pivot[cols_ok]
        pivot["Total"] = pivot.sum(axis=1)
        pivot = pivot.sort_values("Total", ascending=False)
        fig_heat = go.Figure(go.Heatmap(
            z=pivot[cols_ok].values,
            x=[c.split(" ",1)[-1] if " " in c else c for c in cols_ok],
            y=pivot.index.tolist(),
            colorscale="Blues",
            text=pivot[cols_ok].values,
            texttemplate="%{text:,}",
            textfont=dict(size=11),
            hovertemplate="<b>%{y}</b><br>%{x}: %{z:,}<extra></extra>",
            showscale=True,
        ))
        dark(fig_heat, max(300, 60 + len(pivot)*38))
        fig_heat.update_layout(
            xaxis=dict(tickfont=dict(size=10), side="bottom"),
            yaxis=dict(tickfont=dict(size=10), autorange="reversed"),
            margin=dict(l=10, r=10, t=20, b=60),
        )
        st.plotly_chart(fig_heat, use_container_width=True)
        st.dataframe(pivot.style.format("{:,.0f}"),
                     use_container_width=True,
                     height=min(60 + len(pivot)*38, 420))
    else:
        st.info("Sem dados para o cruzamento com os filtros atuais.")

# ════════════════════════════════════════════════════════════════
# ABA 2 — EM ABERTO
# ════════════════════════════════════════════════════════════════
with aba_ab:

    FAIXAS_AB_ORDEM = [
        "⚡ Menos de 5 min",
        "🟢 5 a 30 min",
        "🟡 30 min a 1h",
        "🟠 1h a 4h",
        "🔴 4h a 8h",
        "🔵 8h a 24h (1 dia útil)",
        "⛔ Acima de 1 dia útil",
    ]
    FAIXAS_AB_COLORS = {
        "⚡ Menos de 5 min":        "#6366f1",
        "🟢 5 a 30 min":            "#22c55e",
        "🟡 30 min a 1h":           "#f59e0b",
        "🟠 1h a 4h":               "#fb923c",
        "🔴 4h a 8h":               "#ef4444",
        "🔵 8h a 24h (1 dia útil)": "#3b82f6",
        "⛔ Acima de 1 dia útil":   "#7c3aed",
    }
    FAIXA_STYLE = {
        "⛔ Acima de 1 dia útil":   "background-color:#2d1229; color:#c084fc",
        "🔵 8h a 24h (1 dia útil)": "background-color:#172035; color:#60a5fa",
        "🔴 4h a 8h":               "background-color:#2d1515; color:#f87171",
        "🟠 1h a 4h":               "background-color:#2d1f0a; color:#fb923c",
        "🟡 30 min a 1h":           "background-color:#2a2007; color:#fbbf24",
        "🟢 5 a 30 min":            "background-color:#0f2a1a; color:#4ade80",
        "⚡ Menos de 5 min":        "background-color:#1a1a2e; color:#818cf8",
    }

    st.caption(
        f"🕒 Atualizado em: **{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}** "
        "· Próxima atualização em 5 minutos"
    )

    df_abertos = df[df["Status"].str.lower() == "aberto"].copy()

    if df_abertos.empty:
        st.success("✅ Nenhum atendimento em aberto no período/filtro selecionado.")
    else:
        agora = datetime.now()

        def tempo_aberto_util(abertura):
            if pd.isna(abertura):
                return None
            return minutos_uteis(abertura, agora)

        df_abertos["_min"] = df_abertos["Aberto em"].apply(tempo_aberto_util)

        def faixa_ab(m):
            if m is None or pd.isna(m): return "⚡ Menos de 5 min"
            if m < 5:      return "⚡ Menos de 5 min"
            elif m < 30:   return "🟢 5 a 30 min"
            elif m < 60:   return "🟡 30 min a 1h"
            elif m < 240:  return "🟠 1h a 4h"
            elif m < 480:  return "🔴 4h a 8h"
            elif m < 570:  return "🔵 8h a 24h (1 dia útil)"
            else:          return "⛔ Acima de 1 dia útil"

        def fmt_ab(m):
            if m is None or pd.isna(m): return "—"
            h, mn = int(m // 60), int(m % 60)
            if m / MINUTOS_DIA_UTIL >= 1:
                return f"{m/MINUTOS_DIA_UTIL:.1f}d úteis"
            if h == 0: return f"{mn}min"
            return f"{h}h {mn:02d}min"

        df_abertos["Faixa"]           = df_abertos["_min"].apply(faixa_ab)
        df_abertos["Tempo Decorrido"] = df_abertos["_min"].apply(fmt_ab)
        df_abertos["Aberto em fmt"]   = df_abertos["Aberto em"].dt.strftime("%d/%m/%Y %H:%M")

        # ── KPIs ──────────────────────────────────────────────
        total_ab   = len(df_abertos)
        criticos   = len(df_abertos[df_abertos["Faixa"].isin(
                         ["🔴 4h a 8h","🔵 8h a 24h (1 dia útil)","⛔ Acima de 1 dia útil"])])
        vencidos   = len(df_abertos[df_abertos["Faixa"] == "⛔ Acima de 1 dia útil"])
        tma_ab_str = fmt_minutos(df_abertos["_min"].dropna().mean()) if total_ab > 0 else "—"

        ka1, ka2, ka3, ka4 = st.columns(4)
        with ka1:
            st.markdown(f"""<div class="kpi-card">
                <div class="kpi-label">Em Aberto</div>
                <div class="kpi-value" style="color:#f59e0b">{total_ab:,}</div>
                <div class="kpi-sub">atendimentos pendentes</div>
            </div>""", unsafe_allow_html=True)
        with ka2:
            st.markdown(f"""<div class="kpi-card">
                <div class="kpi-label">🔴 Críticos (acima de 4h)</div>
                <div class="kpi-value" style="color:#ef4444">{criticos:,}</div>
                <div class="kpi-sub">faixas acima de 4h úteis</div>
            </div>""", unsafe_allow_html=True)
        with ka3:
            st.markdown(f"""<div class="kpi-card">
                <div class="kpi-label">⛔ Vencidos (acima de 1 dia)</div>
                <div class="kpi-value" style="color:#7c3aed">{vencidos:,}</div>
                <div class="kpi-sub">acima de 1 dia útil</div>
            </div>""", unsafe_allow_html=True)
        with ka4:
            st.markdown(f"""<div class="kpi-card">
                <div class="kpi-label">Tempo Médio em Aberto</div>
                <div class="kpi-value" style="color:#f97316">{tma_ab_str}</div>
                <div class="kpi-badge">horas úteis</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Faixas de tempo ────────────────────────────────────
        faixa_cnt = (
            df_abertos["Faixa"].value_counts()
            .reindex([f for f in FAIXAS_AB_ORDEM if f in df_abertos["Faixa"].unique()])
            .fillna(0).reset_index()
        )
        faixa_cnt.columns = ["Faixa","Qtd"]
        faixa_cnt["Cor"] = faixa_cnt["Faixa"].map(FAIXAS_AB_COLORS)
        total_f = faixa_cnt["Qtd"].sum()
        faixa_cnt["Label"] = faixa_cnt.apply(
            lambda r: f"{int(r['Qtd']):,}  ({r['Qtd']/total_f*100:.1f}%)"
            if total_f > 0 else f"{int(r['Qtd']):,}", axis=1)

        col_g1, col_g2 = st.columns([3, 2])

        with col_g1:
            st.markdown("#### 📊 Distribuição por Faixa de Tempo (horas úteis em aberto)")
            fig_fab = go.Figure(go.Bar(
                x=faixa_cnt["Faixa"], y=faixa_cnt["Qtd"],
                marker_color=faixa_cnt["Cor"],
                text=faixa_cnt["Label"],
                textposition="outside",
                textfont=dict(size=11, color="#c8d0e0"),
            ))
            dark(fig_fab, 340)
            fig_fab.update_layout(xaxis_title="", yaxis_title="Atendimentos",
                                   xaxis=dict(tickfont=dict(size=10)), showlegend=False)
            st.plotly_chart(fig_fab, use_container_width=True)

        with col_g2:
            st.markdown("#### 🏛️ Faixa por Departamento")
            piv = (df_abertos.groupby(["Departamento","Faixa"])
                   .size().unstack(fill_value=0))
            cols_p = [f for f in FAIXAS_AB_ORDEM if f in piv.columns]
            if cols_p:
                piv = piv[cols_p]
                piv["Total"] = piv.sum(axis=1)
                piv = piv.sort_values("Total", ascending=False)
                fig_piv = go.Figure(go.Heatmap(
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
                dark(fig_piv, 340)
                fig_piv.update_layout(
                    xaxis=dict(tickfont=dict(size=9), side="bottom"),
                    yaxis=dict(tickfont=dict(size=9), autorange="reversed"),
                    margin=dict(l=10, r=10, t=10, b=60),
                )
                st.plotly_chart(fig_piv, use_container_width=True)

        # ── Tabela top 20 ──────────────────────────────────────
        st.markdown("#### 📋 Top 20 Atendimentos Mais Antigos em Aberto")
        cols_tab = ["Protocolo","Atendente","Setor","Aberto em fmt","Tempo Decorrido","Faixa"]
        df_tab = (df_abertos
                  .sort_values("_min", ascending=False)
                  .head(20)[cols_tab]
                  .rename(columns={"Aberto em fmt":"Aberto em","Faixa":"Faixa de Tempo"}))

        # pandas >= 2.1 usa .map() em vez de .applymap()
        try:
            styled = df_tab.style.map(
                lambda v: FAIXA_STYLE.get(str(v), ""), subset=["Faixa de Tempo"])
        except AttributeError:
            styled = df_tab.style.applymap(
                lambda v: FAIXA_STYLE.get(str(v), ""), subset=["Faixa de Tempo"])

        st.dataframe(
            styled.format({"Protocolo": "{}"}),
            use_container_width=True,
            height=min(60 + len(df_tab) * 38, 460),
        )

# ─────────────────────────────────────────────
# Rodapé + Auto-refresh a cada 5 minutos
# ─────────────────────────────────────────────
st.markdown("---")
col_f1, col_f2 = st.columns(2)
with col_f1:
    st.caption(
        f"Dashboard gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} • "
        "Dados: base_atendimento_enriquecida.csv"
    )
with col_f2:
    st.caption(
        "⏱️ Horas úteis: seg–sex, 08:00–17:30 · "
        "Feriados: 02/04, 20/04, 21/04/2026 · Sáb/Dom excluídos"
    )

# Auto-refresh a cada 5 minutos (300 segundos)
time_module.sleep(300)
st.rerun()
