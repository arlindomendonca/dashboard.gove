-- ══════════════════════════════════════════════════════════════
-- SETUP SUPABASE v2 — Sistema de Atendimentos Rio Verde
-- Execute em: Supabase → SQL Editor → New Query
--
-- Mudanças em relação ao v1:
-- ✅ Removida tabela contribuintes (recipient é só telefone, sem UUID)
-- ✅ atendimentos agora tem recipient (telefone), agent_uuid, sector_uuid
-- ✅ Mantém atendentes e setores por UUID da API Gove
-- ══════════════════════════════════════════════════════════════

-- ── 1. Atendentes ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.atendentes (
    uuid        TEXT        PRIMARY KEY,   -- uuid da API Gove
    name        TEXT,
    email       TEXT,
    created_at  TIMESTAMPTZ,
    synced_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.atendentes ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "atend_sel" ON public.atendentes;
DROP POLICY IF EXISTS "atend_ins" ON public.atendentes;
DROP POLICY IF EXISTS "atend_upd" ON public.atendentes;
CREATE POLICY "atend_sel" ON public.atendentes FOR SELECT USING (TRUE);
CREATE POLICY "atend_ins" ON public.atendentes FOR INSERT WITH CHECK (TRUE);
CREATE POLICY "atend_upd" ON public.atendentes FOR UPDATE USING (TRUE);

-- ── 2. Setores ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.setores (
    uuid        TEXT        PRIMARY KEY,   -- uuid da API Gove
    name        TEXT,
    acronym     TEXT,
    synced_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.setores ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "setor_sel" ON public.setores;
DROP POLICY IF EXISTS "setor_ins" ON public.setores;
DROP POLICY IF EXISTS "setor_upd" ON public.setores;
CREATE POLICY "setor_sel" ON public.setores FOR SELECT USING (TRUE);
CREATE POLICY "setor_ins" ON public.setores FOR INSERT WITH CHECK (TRUE);
CREATE POLICY "setor_upd" ON public.setores FOR UPDATE USING (TRUE);

-- ── 3. Atendimentos ──────────────────────────────────────────
-- id = id numérico do chat na API Gove (ex: 8162439)
CREATE TABLE IF NOT EXISTS public.atendimentos (
    id          TEXT        PRIMARY KEY,
    recipient   TEXT,                      -- telefone do contribuinte
    status      TEXT,                      -- "Aberto" | "Encerrado"
    agent_uuid  TEXT REFERENCES public.atendentes(uuid) ON DELETE SET NULL,
    sector_uuid TEXT REFERENCES public.setores(uuid)    ON DELETE SET NULL,
    started_at  TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    rating      TEXT,
    synced_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_atend_status     ON public.atendimentos(status);
CREATE INDEX IF NOT EXISTS idx_atend_started    ON public.atendimentos(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_atend_agent      ON public.atendimentos(agent_uuid);
CREATE INDEX IF NOT EXISTS idx_atend_sector     ON public.atendimentos(sector_uuid);
CREATE INDEX IF NOT EXISTS idx_atend_recipient  ON public.atendimentos(recipient);

ALTER TABLE public.atendimentos ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "atend2_sel" ON public.atendimentos;
DROP POLICY IF EXISTS "atend2_ins" ON public.atendimentos;
DROP POLICY IF EXISTS "atend2_upd" ON public.atendimentos;
CREATE POLICY "atend2_sel" ON public.atendimentos FOR SELECT USING (TRUE);
CREATE POLICY "atend2_ins" ON public.atendimentos FOR INSERT WITH CHECK (TRUE);
CREATE POLICY "atend2_upd" ON public.atendimentos FOR UPDATE USING (TRUE);

-- ── 4. View: atendimentos com nomes ──────────────────────────
CREATE OR REPLACE VIEW public.v_atendimentos AS
SELECT
    a.id,
    a.recipient,
    a.status,
    ag.name         AS atendente_nome,
    ag.email        AS atendente_email,
    s.name          AS setor_nome,
    s.acronym       AS setor_sigla,
    a.started_at,
    a.finished_at,
    a.rating,
    a.synced_at,
    a.updated_at
FROM public.atendimentos a
LEFT JOIN public.atendentes ag ON ag.uuid = a.agent_uuid
LEFT JOIN public.setores    s  ON s.uuid  = a.sector_uuid;

-- ── 5. Verificação ───────────────────────────────────────────
SELECT 'atendentes'   AS tabela, COUNT(*) AS registros FROM public.atendentes
UNION ALL
SELECT 'setores',     COUNT(*) FROM public.setores
UNION ALL
SELECT 'atendimentos',COUNT(*) FROM public.atendimentos;
