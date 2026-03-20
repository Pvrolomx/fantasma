-- ============================================================
-- FANTASMA / OBSERVATORIO - Supabase Schema
-- ============================================================
-- NOTA: Cuenta Supabase FREE compartida con otros proyectos.
-- Todas las tablas usan prefijo "fantasma_" para evitar
-- conflictos con castle-ops, astro4, mi-circulo, etc.
-- 
-- Supabase Free Tier limits:
--   - 500MB database
--   - 1GB file storage
--   - 50K monthly active users
--   - 2GB bandwidth
--
-- Estimado de uso Fantasma:
--   - 1 row/dia x 365 = 365 rows/año (~2MB)
--   - Impacto minimo en la cuenta free
-- ============================================================

-- 1. Tabla principal: snapshot diario del score
CREATE TABLE IF NOT EXISTS fantasma_daily_scores (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    total_score INTEGER NOT NULL,
    raw_score INTEGER NOT NULL,
    max_raw INTEGER NOT NULL DEFAULT 180,
    alert_level TEXT NOT NULL,
    alert_emoji TEXT,
    recommended_action TEXT,
    -- Module scores
    core_mxn_score INTEGER DEFAULT 0,
    global_overlay_score INTEGER DEFAULT 0,
    ormuz_score INTEGER DEFAULT 0,
    mexico_score INTEGER DEFAULT 0,

    -- Protocolo 0
    protocolo_0_active BOOLEAN DEFAULT FALSE,
    protocolo_0_severity TEXT,
    protocolo_0_alerts_count INTEGER DEFAULT 0,

    -- Key signals snapshot (los que mas importan)
    brent_price DECIMAL(8,2),
    gas_eu_price DECIMAL(8,2),
    usdmxn DECIMAL(8,4),
    vix DECIMAL(6,2),
    war_risk_spread DECIMAL(6,2),
    corn_price DECIMAL(8,2),

    -- Active signals count
    active_signals INTEGER DEFAULT 0,

    -- Full report JSON (por si necesitas drill-down)
    full_report JSONB,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Tabla de alertas del Protocolo 0
CREATE TABLE IF NOT EXISTS fantasma_protocolo_alerts (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    date DATE NOT NULL,
    alert_type TEXT NOT NULL,        -- DIVERGENCE, COMPLACENCY, ARTIFICIAL_SUPPORT, DELAYED_IMPACT
    alert_name TEXT NOT NULL,        -- SOFR_vs_CHF, BRENT_vs_VIX, DXY_vs_MXN, BRENT_vs_MXN
    severity TEXT NOT NULL,          -- HIGH, MEDIUM
    message TEXT,
    data JSONB,                      -- Raw alert data
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Tabla para observaciones manuales (Modulo 4 de DeepSeek)
-- "Hoy hable con proveedor de vinos y no hay stock"
CREATE TABLE IF NOT EXISTS fantasma_field_notes (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    category TEXT NOT NULL,          -- escasez, precio, observacion, rumor
    note TEXT NOT NULL,
    severity TEXT DEFAULT 'info',    -- info, warning, critical
    source TEXT,                     -- proveedor, mercado, noticia, personal
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- INDICES para queries rapidos
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_fantasma_daily_date 
    ON fantasma_daily_scores(date DESC);

CREATE INDEX IF NOT EXISTS idx_fantasma_alerts_date 
    ON fantasma_protocolo_alerts(date DESC);

CREATE INDEX IF NOT EXISTS idx_fantasma_notes_date 
    ON fantasma_field_notes(date DESC);

CREATE INDEX IF NOT EXISTS idx_fantasma_notes_category 
    ON fantasma_field_notes(category);

-- ============================================================
-- ROW LEVEL SECURITY (RLS)
-- Protege los datos - solo el service_role key puede escribir
-- El anon key puede leer (para el frontend)
-- ============================================================
ALTER TABLE fantasma_daily_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE fantasma_protocolo_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE fantasma_field_notes ENABLE ROW LEVEL SECURITY;

-- Lectura publica (el dashboard puede leer)
CREATE POLICY "fantasma_daily_read" ON fantasma_daily_scores
    FOR SELECT USING (true);

CREATE POLICY "fantasma_alerts_read" ON fantasma_protocolo_alerts
    FOR SELECT USING (true);

CREATE POLICY "fantasma_notes_read" ON fantasma_field_notes
    FOR SELECT USING (true);

-- Escritura solo via service_role (backend/cron)
CREATE POLICY "fantasma_daily_insert" ON fantasma_daily_scores
    FOR INSERT WITH CHECK (true);

CREATE POLICY "fantasma_alerts_insert" ON fantasma_protocolo_alerts
    FOR INSERT WITH CHECK (true);

CREATE POLICY "fantasma_notes_insert" ON fantasma_field_notes
    FOR INSERT WITH CHECK (true);

CREATE POLICY "fantasma_notes_delete" ON fantasma_field_notes
    FOR DELETE USING (true);

-- ============================================================
-- FUNCTION: Upsert diario (insert or update si ya existe hoy)
-- ============================================================
CREATE OR REPLACE FUNCTION fantasma_upsert_daily(
    p_date DATE,
    p_total_score INTEGER,
    p_raw_score INTEGER,
    p_alert_level TEXT,
    p_alert_emoji TEXT,
    p_recommended_action TEXT,
    p_core_mxn INTEGER,
    p_global INTEGER,
    p_ormuz INTEGER,
    p_mexico INTEGER,
    p_protocolo_active BOOLEAN,
    p_protocolo_severity TEXT,
    p_protocolo_alerts INTEGER,
    p_brent DECIMAL,
    p_gas_eu DECIMAL,
    p_usdmxn DECIMAL,
    p_vix DECIMAL,
    p_war_risk DECIMAL,
    p_corn DECIMAL,
    p_active_signals INTEGER,
    p_full_report JSONB
) RETURNS VOID AS $$
BEGIN
    INSERT INTO fantasma_daily_scores (
        date, total_score, raw_score, alert_level, alert_emoji,
        recommended_action, core_mxn_score, global_overlay_score,
        ormuz_score, mexico_score, protocolo_0_active,
        protocolo_0_severity, protocolo_0_alerts_count,
        brent_price, gas_eu_price, usdmxn, vix,
        war_risk_spread, corn_price, active_signals, full_report
    ) VALUES (
        p_date, p_total_score, p_raw_score, p_alert_level, p_alert_emoji,
        p_recommended_action, p_core_mxn, p_global,
        p_ormuz, p_mexico, p_protocolo_active,
        p_protocolo_severity, p_protocolo_alerts,
        p_brent, p_gas_eu, p_usdmxn, p_vix,
        p_war_risk, p_corn, p_active_signals, p_full_report
    )
    ON CONFLICT (date) DO UPDATE SET
        total_score = p_total_score,
        raw_score = p_raw_score,
        alert_level = p_alert_level,
        alert_emoji = p_alert_emoji,
        recommended_action = p_recommended_action,
        core_mxn_score = p_core_mxn,
        global_overlay_score = p_global,
        ormuz_score = p_ormuz,
        mexico_score = p_mexico,
        protocolo_0_active = p_protocolo_active,
        protocolo_0_severity = p_protocolo_severity,
        protocolo_0_alerts_count = p_protocolo_alerts,
        brent_price = p_brent,
        gas_eu_price = p_gas_eu,
        usdmxn = p_usdmxn,
        vix = p_vix,
        war_risk_spread = p_war_risk,
        corn_price = p_corn,
        active_signals = p_active_signals,
        full_report = p_full_report,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- VISTA: Resumen rapido para el dashboard
-- ============================================================
CREATE OR REPLACE VIEW fantasma_dashboard AS
SELECT 
    date,
    total_score,
    alert_level,
    alert_emoji,
    core_mxn_score,
    global_overlay_score,
    ormuz_score,
    mexico_score,
    protocolo_0_active,
    brent_price,
    usdmxn,
    vix,
    active_signals,
    -- Cambio vs dia anterior
    total_score - LAG(total_score) OVER (ORDER BY date) AS score_change,
    brent_price - LAG(brent_price) OVER (ORDER BY date) AS brent_change,
    usdmxn - LAG(usdmxn) OVER (ORDER BY date) AS usdmxn_change
FROM fantasma_daily_scores
ORDER BY date DESC;

-- ============================================================
-- EJEMPLO DE USO
-- ============================================================
-- Leer ultimos 30 dias:
--   SELECT * FROM fantasma_dashboard LIMIT 30;
--
-- Dias con Protocolo 0 activo:
--   SELECT * FROM fantasma_daily_scores WHERE protocolo_0_active = true ORDER BY date DESC;
--
-- Notas de campo de esta semana:
--   SELECT * FROM fantasma_field_notes WHERE date >= CURRENT_DATE - 7 ORDER BY date DESC;
--
-- Agregar nota manual:
--   INSERT INTO fantasma_field_notes (category, note, severity, source)
--   VALUES ('escasez', 'Proveedor de vinos sin stock de europeos', 'warning', 'proveedor');
