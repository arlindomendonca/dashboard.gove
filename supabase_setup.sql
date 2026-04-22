-- ══════════════════════════════════════════════════════════════
-- SETUP SUPABASE — Sistema de Atendimentos Rio Verde
-- Execute no Supabase: painel → SQL Editor → New Query
-- ══════════════════════════════════════════════════════════════

-- ── 1. Tabela de usuários (estende auth.users) ────────────────
CREATE TABLE IF NOT EXISTS public.profiles (
    id         UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email      TEXT NOT NULL,
    nome       TEXT NOT NULL,
    ativo      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- RLS: usuário só lê e edita o próprio perfil
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "leitura_proprio_perfil" ON public.profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "atualizacao_proprio_perfil" ON public.profiles
    FOR UPDATE USING (auth.uid() = id);

-- Trigger: cria perfil automaticamente ao cadastrar usuário
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, nome)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(
            NEW.raw_user_meta_data->>'nome',
            SPLIT_PART(NEW.email, '@', 1)
        )
    )
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ── 2. Tabela de logs de atendimentos ────────────────────────
CREATE TABLE IF NOT EXISTS public.atendimento_logs (
    id              BIGSERIAL PRIMARY KEY,
    protocolo       TEXT,
    status          TEXT,
    setor           TEXT,
    atendente       TEXT,
    aberto_em       TIMESTAMPTZ,
    encerrado_em    TIMESTAMPTZ,
    tempo_util_min  NUMERIC(10,2),
    faixa_tempo     TEXT,
    fonte           TEXT DEFAULT 'api_gove',
    snapshot_em     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_logs_protocolo   ON public.atendimento_logs(protocolo);
CREATE INDEX IF NOT EXISTS idx_logs_snapshot    ON public.atendimento_logs(snapshot_em DESC);
CREATE INDEX IF NOT EXISTS idx_logs_setor       ON public.atendimento_logs(setor);
CREATE INDEX IF NOT EXISTS idx_logs_faixa       ON public.atendimento_logs(faixa_tempo);

-- RLS: qualquer usuário autenticado lê e insere logs
ALTER TABLE public.atendimento_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "autenticados_leem_logs" ON public.atendimento_logs
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "autenticados_inserem_logs" ON public.atendimento_logs
    FOR INSERT WITH CHECK (auth.role() = 'authenticated');

-- ── 3. View: métricas diárias ────────────────────────────────
CREATE OR REPLACE VIEW public.v_metricas_diarias AS
SELECT
    DATE(snapshot_em AT TIME ZONE 'America/Sao_Paulo') AS dia,
    COUNT(*)                                            AS total_snapshots,
    COUNT(DISTINCT protocolo)                           AS total_protocolos,
    COUNT(*) FILTER (
        WHERE faixa_tempo IN (
            '🔴 4h a 8h',
            '🔵 8h a 24h (1 dia útil)',
            '⛔ Acima de 1 dia útil'
        )
    )                                                   AS criticos,
    COUNT(*) FILTER (
        WHERE faixa_tempo = '⛔ Acima de 1 dia útil'
    )                                                   AS vencidos,
    ROUND(AVG(tempo_util_min)::NUMERIC, 1)              AS tma_medio_min,
    MAX(snapshot_em)                                    AS ultimo_snapshot
FROM public.atendimento_logs
GROUP BY DATE(snapshot_em AT TIME ZONE 'America/Sao_Paulo')
ORDER BY dia DESC;

-- ── 4. View: distribuição por faixa (últimas 24h) ────────────
CREATE OR REPLACE VIEW public.v_faixas_recentes AS
SELECT
    faixa_tempo,
    setor,
    COUNT(DISTINCT protocolo) AS qtd
FROM public.atendimento_logs
WHERE snapshot_em >= NOW() - INTERVAL '24 hours'
GROUP BY faixa_tempo, setor
ORDER BY qtd DESC;

-- ── 5. Como adicionar usuários ───────────────────────────────
-- Opção A (recomendada): Supabase Auth → Authentication → Users → "Add user"
-- Preencha e-mail e senha. O trigger cria o perfil automaticamente.

-- Opção B: via SQL (requer senha hasheada — use o painel)
-- Após criar via painel, personalize o nome:
/*
UPDATE public.profiles
SET nome = 'Nome Completo'
WHERE email = 'usuario@email.com';
*/

-- ── 6. Verificação ───────────────────────────────────────────
SELECT 'profiles' AS tabela, COUNT(*) AS registros FROM public.profiles
UNION ALL
SELECT 'atendimento_logs', COUNT(*) FROM public.atendimento_logs;
