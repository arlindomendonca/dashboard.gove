import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date

# ─────────────────────────────────────────────
# Configuração da Página
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Dashboard de Atendimentos",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS customizado para visual moderno
st.markdown("""
<style>
    /* Fundo geral */
    .stApp { background-color: #0f1117; }
    section[data-testid="stSidebar"] { background-color: #1a1d27; }

    /* Cards KPI */
    .kpi-card {
        background: linear-gradient(135deg, #1e2130, #252a3d);
        border: 1px solid #2e3450;
        border-radius: 12px;
        padding: 20px 24px;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    .kpi-label {
        font-size: 13px;
        color: #8b92a5;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 6px;
    }
    .kpi-value {
        font-size: 32px;
        font-weight: 700;
        color: #ffffff;
        line-height: 1.1;
    }
    .kpi-sub {
        font-size: 12px;
        color: #5c6880;
        margin-top: 4px;
    }
    .kpi-delta-pos { color: #22c55e; font-size: 13px; margin-top: 4px; }
    .kpi-delta-neg { color: #ef4444; font-size: 13px; margin-top: 4px; }

    /* Título principal */
    .main-title {
        font-size: 28px;
        font-weight: 800;
        color: #e2e8f0;
        margin-bottom: 4px;
    }
    .main-subtitle {
        font-size: 14px;
        color: #64748b;
        margin-bottom: 28px;
    }

    /* Divider */
    hr { border-color: #2e3450; }

    /* Plotly backgrounds */
    .js-plotly-plot .plotly { border-radius: 12px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Carregamento e Limpeza dos Dados
# ─────────────────────────────────────────────
@st.cache_data(show_spinner="Carregando base de atendimentos...")
def load_data(filepath: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(
            filepath,
            sep=";",
            encoding="utf-8-sig",
            low_memory=False,
            dtype=str,
        )
    except Exception:
        df = pd.read_csv(
            filepath,
            sep=";",
            encoding="latin1",
            low_memory=False,
            dtype=str,
        )

    # Remove linhas completamente vazias
    df.dropna(how="all", inplace=True)

    # Normaliza nomes de colunas (remove espaços extras)
    df.columns = df.columns.str.strip()

    # Converte datas
    for col in ["Aberto em", "Encerrado em"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], format="%d/%m/%Y %H:%M", errors="coerce")

    # Converte Tempo Atendimento para segundos totais
    def parse_tempo(val):
        if pd.isna(val) or str(val).strip() in ("", "nan"):
            return None
        try:
            parts = str(val).strip().split(":")
            if len(parts) == 3:
                h, m, s = int(parts[0]), int(parts[1]), int(float(parts[2]))
                return h * 3600 + m * 60 + s
        except Exception:
            return None

    if "Tempo Atendimento" in df.columns:
        df["Tempo_seg"] = df["Tempo Atendimento"].apply(parse_tempo)

    # Garante coluna Protocolo como string limpa
    if "Protocolo" in df.columns:
        df["Protocolo"] = df["Protocolo"].astype(str).str.strip()

    # Limpa Status e Atendente
    for col in ["Status", "Atendente", "Setor"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    return df


# ─────────────────────────────────────────────
# Carrega dados
# ─────────────────────────────────────────────
DATA_PATH = "base_atendimento.csv"

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
    st.markdown("---")

    # Período
    min_date = df_raw["Aberto em"].min().date() if df_raw["Aberto em"].notna().any() else date.today()
    max_date = df_raw["Aberto em"].max().date() if df_raw["Aberto em"].notna().any() else date.today()

    st.markdown("**📅 Período de Abertura**")
    date_ini = st.date_input("De", value=min_date, min_value=min_date, max_value=max_date)
    date_fim = st.date_input("Até", value=max_date, min_value=min_date, max_value=max_date)

    st.markdown("---")

    # Setor
    setores_disponiveis = sorted(
        [s for s in df_raw["Setor"].dropna().unique() if s not in ("nan", "")]
    )
    setores_sel = st.multiselect(
        "🏢 Setor",
        options=setores_disponiveis,
        default=[],
        placeholder="Todos os setores",
    )

    st.markdown("---")

    # Status
    status_disponiveis = sorted(
        [s for s in df_raw["Status"].dropna().unique() if s not in ("nan", "")]
    )
    status_sel = st.multiselect(
        "🔖 Status",
        options=status_disponiveis,
        default=[],
        placeholder="Todos os status",
    )

    st.markdown("---")
    st.caption(f"Base carregada: **{len(df_raw):,}** registros")

# ─────────────────────────────────────────────
# Aplica Filtros
# ─────────────────────────────────────────────
df = df_raw.copy()

# Filtro de período
df = df[
    (df["Aberto em"].dt.date >= date_ini) &
    (df["Aberto em"].dt.date <= date_fim)
]

# Filtro de setor
if setores_sel:
    df = df[df["Setor"].isin(setores_sel)]

# Filtro de status
if status_sel:
    df = df[df["Status"].isin(status_sel)]

# ─────────────────────────────────────────────
# Cabeçalho
# ─────────────────────────────────────────────
st.markdown('<div class="main-title">📊 Dashboard de Atendimentos</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="main-subtitle">Período: {date_ini.strftime("%d/%m/%Y")} a {date_fim.strftime("%d/%m/%Y")} '
    f'&nbsp;|&nbsp; Registros filtrados: <b>{len(df):,}</b></div>',
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────
# KPIs
# ─────────────────────────────────────────────
total = len(df)
encerrados = df[df["Status"].str.lower() == "encerrado"]
pct_enc = (len(encerrados) / total * 100) if total > 0 else 0

tma_seg = df["Tempo_seg"].dropna()
tma_media_seg = tma_seg.mean() if len(tma_seg) > 0 else 0
tma_min = tma_media_seg / 60
if tma_min >= 60:
    tma_str = f"{tma_min/60:.1f}h"
else:
    tma_str = f"{tma_min:.1f} min"

# Volume hoje vs média diária
hoje = date.today()
vol_hoje = len(df[df["Aberto em"].dt.date == hoje])
dias_unicos = df["Aberto em"].dt.date.nunique()
media_diaria = total / dias_unicos if dias_unicos > 0 else 0
delta_hoje = vol_hoje - media_diaria
delta_pct = (delta_hoje / media_diaria * 100) if media_diaria > 0 else 0

k1, k2, k3, k4 = st.columns(4)

with k1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Total de Atendimentos</div>
        <div class="kpi-value">{total:,}</div>
        <div class="kpi-sub">no período selecionado</div>
    </div>""", unsafe_allow_html=True)

with k2:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">% Encerrados</div>
        <div class="kpi-value">{pct_enc:.1f}%</div>
        <div class="kpi-sub">{len(encerrados):,} de {total:,}</div>
    </div>""", unsafe_allow_html=True)

with k3:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">TMA (Tempo Médio)</div>
        <div class="kpi-value">{tma_str}</div>
        <div class="kpi-sub">com base em encerrados</div>
    </div>""", unsafe_allow_html=True)

with k4:
    delta_class = "kpi-delta-pos" if delta_hoje >= 0 else "kpi-delta-neg"
    delta_icon = "▲" if delta_hoje >= 0 else "▼"
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Hoje vs Média Diária</div>
        <div class="kpi-value">{vol_hoje:,}</div>
        <div class="{delta_class}">{delta_icon} {abs(delta_pct):.1f}% vs média ({media_diaria:.0f}/dia)</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Configuração visual dos gráficos
# ─────────────────────────────────────────────
CHART_BG = "#1a1d27"
PAPER_BG = "#1a1d27"
FONT_COLOR = "#c8d0e0"
GRID_COLOR = "#2e3450"

def apply_dark_theme(fig):
    fig.update_layout(
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=CHART_BG,
        font=dict(color=FONT_COLOR, family="Inter, sans-serif"),
        xaxis=dict(gridcolor=GRID_COLOR, linecolor=GRID_COLOR, tickfont=dict(size=11)),
        yaxis=dict(gridcolor=GRID_COLOR, linecolor=GRID_COLOR, tickfont=dict(size=11)),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=12)),
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig

# ─────────────────────────────────────────────
# Linha 1: Volume Temporal | Distribuição Status
# ─────────────────────────────────────────────
col_l, col_r = st.columns([3, 1])

with col_l:
    st.markdown("#### 📈 Volume Temporal de Atendimentos")

    # Agrupa por dia
    vol_dia = (
        df.set_index("Aberto em")
        .resample("D")
        .size()
        .reset_index(name="Quantidade")
    )
    vol_dia.columns = ["Data", "Quantidade"]

    if len(vol_dia) > 1:
        fig_line = px.line(
            vol_dia,
            x="Data",
            y="Quantidade",
            markers=True,
            color_discrete_sequence=["#6366f1"],
        )
        fig_line.update_traces(
            line=dict(width=2.5),
            marker=dict(size=6),
            fill="tozeroy",
            fillcolor="rgba(99,102,241,0.12)",
        )
    else:
        # Agrupa por hora quando há apenas 1 dia
        vol_hora = (
            df.set_index("Aberto em")
            .resample("h")
            .size()
            .reset_index(name="Quantidade")
        )
        vol_hora.columns = ["Hora", "Quantidade"]
        fig_line = px.bar(
            vol_hora,
            x="Hora",
            y="Quantidade",
            color_discrete_sequence=["#6366f1"],
        )

    apply_dark_theme(fig_line)
    fig_line.update_layout(xaxis_title="", yaxis_title="Chamados", height=300)
    st.plotly_chart(fig_line, use_container_width=True)

with col_r:
    st.markdown("#### 🍩 Status")
    status_count = df["Status"].value_counts().reset_index()
    status_count.columns = ["Status", "Qtd"]

    colors_pie = ["#6366f1", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6"]
    fig_pie = go.Figure(go.Pie(
        labels=status_count["Status"],
        values=status_count["Qtd"],
        hole=0.55,
        marker=dict(colors=colors_pie[:len(status_count)]),
        textfont=dict(size=12, color="#ffffff"),
        insidetextorientation="horizontal",
    ))
    apply_dark_theme(fig_pie)
    fig_pie.update_layout(
        showlegend=True,
        legend=dict(orientation="v", x=0, y=0.5, font=dict(size=11)),
        height=300,
        margin=dict(l=0, r=0, t=40, b=0),
    )
    st.plotly_chart(fig_pie, use_container_width=True)

# ─────────────────────────────────────────────
# Linha 2: Top Setores | Desempenho Atendentes
# ─────────────────────────────────────────────
col_a, col_b = st.columns(2)

with col_a:
    st.markdown("#### 🏢 Top 10 Setores Mais Demandados")
    top_setores = (
        df[~df["Setor"].isin(["-", "nan", ""])]
        ["Setor"]
        .value_counts()
        .head(10)
        .reset_index()
    )
    top_setores.columns = ["Setor", "Qtd"]
    top_setores = top_setores.sort_values("Qtd", ascending=True)

    # Trunca nomes longos
    top_setores["Setor_curto"] = top_setores["Setor"].apply(
        lambda x: x[:45] + "…" if len(x) > 45 else x
    )

    fig_bar_h = px.bar(
        top_setores,
        x="Qtd",
        y="Setor_curto",
        orientation="h",
        color="Qtd",
        color_continuous_scale=["#312e81", "#6366f1", "#a5b4fc"],
        text="Qtd",
    )
    fig_bar_h.update_traces(textposition="outside", textfont=dict(size=11, color=FONT_COLOR))
    apply_dark_theme(fig_bar_h)
    fig_bar_h.update_layout(
        height=420,
        yaxis_title="",
        xaxis_title="Quantidade",
        coloraxis_showscale=False,
        yaxis=dict(tickfont=dict(size=10)),
    )
    st.plotly_chart(fig_bar_h, use_container_width=True)

with col_b:
    st.markdown("#### 👤 Desempenho por Atendente (Top 15)")
    top_atendentes = (
        df[~df["Atendente"].isin(["nan", "NÃO ATRIBUIDO", ""])]
        ["Atendente"]
        .value_counts()
        .head(15)
        .reset_index()
    )
    top_atendentes.columns = ["Atendente", "Qtd"]
    top_atendentes = top_atendentes.sort_values("Qtd", ascending=False)

    fig_bar_v = px.bar(
        top_atendentes,
        x="Atendente",
        y="Qtd",
        color="Qtd",
        color_continuous_scale=["#134e4a", "#10b981", "#6ee7b7"],
        text="Qtd",
    )
    fig_bar_v.update_traces(textposition="outside", textfont=dict(size=11, color=FONT_COLOR))
    apply_dark_theme(fig_bar_v)
    fig_bar_v.update_layout(
        height=420,
        xaxis_title="",
        yaxis_title="Atendimentos",
        coloraxis_showscale=False,
        xaxis=dict(tickangle=-35, tickfont=dict(size=10)),
    )
    st.plotly_chart(fig_bar_v, use_container_width=True)

# ─────────────────────────────────────────────
# Linha 3: TMA por Setor
# ─────────────────────────────────────────────
st.markdown("#### ⏱️ Tempo Médio de Atendimento (TMA) por Setor – Top 10")
tma_setor = (
    df[~df["Setor"].isin(["-", "nan", ""])]
    .groupby("Setor")["Tempo_seg"]
    .mean()
    .dropna()
    .sort_values(ascending=False)
    .head(10)
    .reset_index()
)
tma_setor.columns = ["Setor", "TMA_seg"]
tma_setor["TMA_min"] = (tma_setor["TMA_seg"] / 60).round(1)
tma_setor["Setor_curto"] = tma_setor["Setor"].apply(
    lambda x: x[:45] + "…" if len(x) > 45 else x
)
tma_setor = tma_setor.sort_values("TMA_min", ascending=True)

fig_tma = px.bar(
    tma_setor,
    x="TMA_min",
    y="Setor_curto",
    orientation="h",
    color="TMA_min",
    color_continuous_scale=["#7c2d12", "#f97316", "#fed7aa"],
    text=tma_setor["TMA_min"].apply(lambda x: f"{x:.1f} min"),
)
fig_tma.update_traces(textposition="outside", textfont=dict(size=11, color=FONT_COLOR))
apply_dark_theme(fig_tma)
fig_tma.update_layout(
    height=360,
    xaxis_title="Minutos",
    yaxis_title="",
    coloraxis_showscale=False,
    yaxis=dict(tickfont=dict(size=10)),
)
st.plotly_chart(fig_tma, use_container_width=True)

# ─────────────────────────────────────────────
# Rodapé
# ─────────────────────────────────────────────
st.markdown("---")
st.caption(
    f"Dashboard gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} • "
    "Dados: base_atendimento.csv"
)
