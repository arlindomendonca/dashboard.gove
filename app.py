import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, time, timedelta

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
    # Garante que são objetos date Python puros (nunca NaT)
    if pd.isna(min_date): min_date = _fallback
    if pd.isna(max_date): max_date = _fallback

    st.markdown('<div class="section-title">📅 Período de Abertura</div>', unsafe_allow_html=True)
    date_ini = st.date_input("De", value=min_date, min_value=min_date, max_value=max_date)
    date_fim = st.date_input("Até", value=max_date, min_value=min_date, max_value=max_date)
    st.markdown("---")

    CHATBOT_LABEL = "Chatbot / Inatividade"
    ver_chatbot = st.checkbox("🤖 Ver Chatbot / Inatividade", value=False)
    st.markdown("---")

    deptos_disp = sorted([d for d in df_raw["Departamento"].dropna().unique()
                          if d not in ("nan", "", CHATBOT_LABEL)])
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
# Exclui Chatbot/Inatividade por padrão (a menos que checkbox esteja marcado)
if not ver_chatbot:
    df = df[df["Departamento"] != "Chatbot / Inatividade"]
if deptos_sel:
    df = df[df["Departamento"].isin(deptos_sel)]
if setores_sel:
    df = df[df["Setor"].isin(setores_sel)]
if status_sel:
    df = df[df["Status"].isin(status_sel)]
if faixas_sel:
    df = df[df["Faixa de Tempo"].isin(faixas_sel)]

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
# KPIs
# ─────────────────────────────────────────────
total = len(df)
encerrados = df[df["Status"].str.lower() == "encerrado"]
pct_enc = (len(encerrados) / total * 100) if total > 0 else 0

tma_s = df["Tempo_util_min"].dropna()
tma_media = tma_s.mean() if len(tma_s) > 0 else 0
tma_str = fmt_minutos(tma_media)

hoje = date.today()
# Conta apenas dias úteis no período para a média
all_days = pd.date_range(date_ini, date_fim)
dias_uteis_periodo = sum(1 for d in all_days if is_dia_util(d.date()))
vol_hoje = len(df[df["Aberto em"].dt.date == hoje])
dias_uteis_periodo = max(dias_uteis_periodo, 1)
media_diaria = total / dias_uteis_periodo
delta_pct = ((vol_hoje - media_diaria) / media_diaria * 100) if media_diaria > 0 else 0

# KPI extra: % dentro de 1h (SLA)
dentro_sla = len(df[df["Faixa de Tempo"].isin(["⚡ Menos de 5 min","🟢 5 a 30 min","🟡 30 min a 1h"])])
pct_sla = (dentro_sla / len(encerrados) * 100) if len(encerrados) > 0 else 0

k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-label">Total de Atendimentos</div>
        <div class="kpi-value">{total:,}</div>
        <div class="kpi-sub">no período</div>
    </div>""", unsafe_allow_html=True)
with k2:
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-label">% Encerrados</div>
        <div class="kpi-value">{pct_enc:.1f}%</div>
        <div class="kpi-sub">{len(encerrados):,} de {total:,}</div>
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
    sla_class = "kpi-delta-pos" if pct_sla >= 70 else "kpi-delta-neg"
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-label">SLA ≤ 1h (horas úteis)</div>
        <div class="kpi-value">{pct_sla:.1f}%</div>
        <div class="{sla_class}">{dentro_sla:,} atendimentos</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Helper tema escuro
# ─────────────────────────────────────────────
def dark(fig, height=320):
    fig.update_layout(
        paper_bgcolor="#1a1d27", plot_bgcolor="#1a1d27",
        font=dict(color="#c8d0e0", family="Inter, sans-serif"),
        xaxis=dict(gridcolor="#2e3450", linecolor="#2e3450", tickfont=dict(size=11)),
        yaxis=dict(gridcolor="#2e3450", linecolor="#2e3450", tickfont=dict(size=11)),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=12)),
        margin=dict(l=10, r=10, t=40, b=10),
        height=height,
    )
    return fig

FC = "#c8d0e0"

# ─────────────────────────────────────────────
# Linha 1: Volume Temporal | Status Rosca
# ─────────────────────────────────────────────
col_l, col_r = st.columns([3, 1])

with col_l:
    st.markdown("#### 📈 Volume Temporal de Atendimentos (dias úteis)")
    vol_dia = (df.set_index("Aberto em").resample("D").size()
               .reset_index(name="Quantidade"))
    vol_dia.columns = ["Data", "Quantidade"]
    # Marca fins de semana / feriados
    vol_dia["Dia Útil"] = vol_dia["Data"].dt.date.apply(is_dia_util)

    if len(vol_dia) > 1:
        fig_line = px.line(vol_dia, x="Data", y="Quantidade", markers=True,
                           color_discrete_sequence=["#6366f1"])
        fig_line.update_traces(line=dict(width=2.5), marker=dict(size=6),
                                fill="tozeroy", fillcolor="rgba(99,102,241,0.12)")
        # Destaca não-úteis com fundo vermelho suave
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
    st.markdown("#### 🍩 Status")
    sc = df["Status"].value_counts().reset_index()
    sc.columns = ["Status", "Qtd"]
    fig_pie = go.Figure(go.Pie(
        labels=sc["Status"], values=sc["Qtd"], hole=0.55,
        marker=dict(colors=["#6366f1","#22c55e","#f59e0b","#ef4444","#8b5cf6"]),
        textfont=dict(size=12, color="#ffffff"), insidetextorientation="horizontal",
    ))
    dark(fig_pie, 300)
    fig_pie.update_layout(showlegend=True,
        legend=dict(orientation="v", x=0, y=0.5, font=dict(size=11)),
        margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig_pie, use_container_width=True)

# ─────────────────────────────────────────────
# Linha 2: Faixa de Tempo Útil | Departamentos
# ─────────────────────────────────────────────
col_a, col_b = st.columns(2)

with col_a:
    st.markdown("#### ⏱️ Distribuição por Faixa de Tempo Útil")
    df_faixa = df[~df["Faixa de Tempo"].isin(["N/A", "nan"])]
    faixa_count = (
        df_faixa["Faixa de Tempo"]
        .value_counts()
        .reindex([f for f in FAIXAS_ORDEM if f in df_faixa["Faixa de Tempo"].unique()])
        .fillna(0).reset_index()
    )
    faixa_count.columns = ["Faixa", "Qtd"]
    faixa_count["Cor"] = faixa_count["Faixa"].map(FAIXA_COLORS)

    fig_faixa = go.Figure(go.Bar(
        x=faixa_count["Faixa"], y=faixa_count["Qtd"],
        marker_color=faixa_count["Cor"],
        text=faixa_count["Qtd"].apply(lambda x: f"{int(x):,}"),
        textposition="outside", textfont=dict(size=11, color=FC),
    ))
    dark(fig_faixa, 360)
    fig_faixa.update_layout(xaxis_title="", yaxis_title="Atendimentos",
                             xaxis=dict(tickfont=dict(size=10)))
    st.plotly_chart(fig_faixa, use_container_width=True)

with col_b:
    st.markdown("#### 🏛️ Atendimentos por Departamento")
    df_dep = df[~df["Departamento"].isin(["nan", ""])]
    depto_cnt = df_dep["Departamento"].value_counts().head(15).reset_index()
    depto_cnt.columns = ["Departamento", "Qtd"]
    depto_cnt = depto_cnt.sort_values("Qtd", ascending=True)

    fig_dep = px.bar(depto_cnt, x="Qtd", y="Departamento", orientation="h",
                     color="Qtd",
                     color_continuous_scale=["#1e3a5f","#3b82f6","#93c5fd"],
                     text="Qtd")
    fig_dep.update_traces(textposition="outside", textfont=dict(size=11, color=FC))
    dark(fig_dep, 360)
    fig_dep.update_layout(xaxis_title="Quantidade", yaxis_title="",
                          coloraxis_showscale=False,
                          yaxis=dict(tickfont=dict(size=10)))
    st.plotly_chart(fig_dep, use_container_width=True)

# ─────────────────────────────────────────────
# Linha 3: Top Setores | Top Atendentes
# ─────────────────────────────────────────────
col_c, col_d = st.columns(2)

with col_c:
    st.markdown("#### 🏢 Top 10 Setores Mais Demandados")
    top_set = (df[~df["Setor"].isin(["-","nan",""])]
               ["Setor"].value_counts().head(10).reset_index())
    top_set.columns = ["Setor", "Qtd"]
    top_set = top_set.sort_values("Qtd", ascending=True)
    top_set["Setor_curto"] = top_set["Setor"].apply(
        lambda x: x[:42] + "…" if len(x) > 42 else x)
    fig_set = px.bar(top_set, x="Qtd", y="Setor_curto", orientation="h",
                     color="Qtd",
                     color_continuous_scale=["#312e81","#6366f1","#a5b4fc"],
                     text="Qtd")
    fig_set.update_traces(textposition="outside", textfont=dict(size=11, color=FC))
    dark(fig_set, 380)
    fig_set.update_layout(xaxis_title="Quantidade", yaxis_title="",
                          coloraxis_showscale=False,
                          yaxis=dict(tickfont=dict(size=10)))
    st.plotly_chart(fig_set, use_container_width=True)

with col_d:
    st.markdown("#### 👤 Top 15 Atendentes")
    top_at = (df[~df["Atendente"].isin(["nan","NÃO ATRIBUIDO",""])]
              ["Atendente"].value_counts().head(15).reset_index())
    top_at.columns = ["Atendente", "Qtd"]
    top_at = top_at.sort_values("Qtd", ascending=False)
    fig_at = px.bar(top_at, x="Atendente", y="Qtd", color="Qtd",
                    color_continuous_scale=["#134e4a","#10b981","#6ee7b7"],
                    text="Qtd")
    fig_at.update_traces(textposition="outside", textfont=dict(size=11, color=FC))
    dark(fig_at, 380)
    fig_at.update_layout(xaxis_title="", yaxis_title="Atendimentos",
                         coloraxis_showscale=False,
                         xaxis=dict(tickangle=-35, tickfont=dict(size=10)))
    st.plotly_chart(fig_at, use_container_width=True)

# ─────────────────────────────────────────────
# Linha 4: TMA por Departamento (horas úteis)
# ─────────────────────────────────────────────
st.markdown("#### ⏱️ TMA Médio por Departamento — em horas úteis (08:00–17:30)")

df_tma = (
    df[
        (df["Status"].str.lower() == "encerrado") &
        (~df["Departamento"].isin(["nan","Chatbot / Inatividade"]))
    ]
    .groupby("Departamento")["Tempo_util_min"].mean()
    .dropna().sort_values(ascending=False).head(12).reset_index()
)
df_tma.columns = ["Departamento", "TMA_min"]
df_tma["Label"] = df_tma["TMA_min"].apply(fmt_minutos)
df_tma = df_tma.sort_values("TMA_min", ascending=True)

fig_tma = px.bar(df_tma, x="TMA_min", y="Departamento", orientation="h",
                 color="TMA_min",
                 color_continuous_scale=["#7c2d12","#f97316","#fed7aa"],
                 text="Label")
fig_tma.update_traces(textposition="outside", textfont=dict(size=11, color=FC))
dark(fig_tma, 400)
fig_tma.update_layout(xaxis_title="Minutos úteis", yaxis_title="",
                      coloraxis_showscale=False,
                      yaxis=dict(tickfont=dict(size=10)))
st.plotly_chart(fig_tma, use_container_width=True)

# ─────────────────────────────────────────────
# Linha 5: Cruzamento Faixa × Departamento
# ─────────────────────────────────────────────
st.markdown("#### 📋 Cruzamento: Faixa de Tempo Útil × Departamento")

df_cross = df[~df["Faixa de Tempo"].isin(["N/A", "nan", "Sem registro"])]
if not df_cross.empty:
    pivot = (df_cross.groupby(["Departamento","Faixa de Tempo"])
             .size().unstack(fill_value=0))
    cols_ok = [f for f in FAIXAS_ORDEM if f in pivot.columns]
    pivot = pivot[cols_ok]
    pivot["Total"] = pivot.sum(axis=1)
    pivot = pivot.sort_values("Total", ascending=False)

    # Heatmap via Plotly (sem matplotlib)
    fig_heat = go.Figure(go.Heatmap(
        z=pivot[cols_ok].values,
        x=[c.split(" ", 1)[-1] if " " in c else c for c in cols_ok],
        y=pivot.index.tolist(),
        colorscale="Blues",
        text=pivot[cols_ok].values,
        texttemplate="%{text:,}",
        textfont=dict(size=11),
        hovertemplate="<b>%{y}</b><br>%{x}: %{z:,}<extra></extra>",
        showscale=True,
    ))
    dark(fig_heat, max(300, 60 + len(pivot) * 38))
    fig_heat.update_layout(
        xaxis=dict(tickfont=dict(size=10), side="bottom"),
        yaxis=dict(tickfont=dict(size=10), autorange="reversed"),
        margin=dict(l=10, r=10, t=20, b=60),
    )
    st.plotly_chart(fig_heat, use_container_width=True)

    # Tabela simples sem gradient (sem matplotlib)
    st.dataframe(
        pivot.style.format("{:,.0f}"),
        use_container_width=True,
        height=min(60 + len(pivot) * 38, 420),
    )
else:
    st.info("Sem dados para o cruzamento com os filtros atuais.")

# ─────────────────────────────────────────────
# Rodapé
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
