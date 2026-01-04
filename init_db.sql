-- Создание базы данных (выполни вручную в psql или pgAdmin)
-- CREATE DATABASE trading_journal;

-- Таблица сделок
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    trade_date DATE NOT NULL,
    trade_time TIME NOT NULL,
    pair VARCHAR(20) NOT NULL,
    trade_type VARCHAR(10) NOT NULL CHECK (trade_type IN ('long', 'short', 'лонг', 'шорт')),
    entry_price NUMERIC(20, 8) NOT NULL,
    exit_price NUMERIC(20, 8) NOT NULL,
    position_size NUMERIC(20, 8),
    pnl_usd NUMERIC(20, 2) NOT NULL,
    pnl_pct NUMERIC(10, 2) NOT NULL,
    category VARCHAR(20) NOT NULL CHECK (category IN ('стратегия', 'импульс', 'неизвестно')),
    tags TEXT,
    comment TEXT
);

-- Индексы для быстрых запросов
CREATE INDEX idx_trades_date ON trades(trade_date DESC);
CREATE INDEX idx_trades_category ON trades(category);
CREATE INDEX idx_trades_created_at ON trades(created_at DESC);

-- Таблица для метрик (опционально, для кеширования)
CREATE TABLE IF NOT EXISTS daily_stats (
    id SERIAL PRIMARY KEY,
    stat_date DATE UNIQUE NOT NULL,
    total_trades INTEGER DEFAULT 0,
    strategy_trades INTEGER DEFAULT 0,
    impulse_trades INTEGER DEFAULT 0,
    total_pnl NUMERIC(20, 2) DEFAULT 0,
    strategy_pnl NUMERIC(20, 2) DEFAULT 0,
    impulse_pnl NUMERIC(20, 2) DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Представление для удобной аналитики
CREATE OR REPLACE VIEW trades_summary AS
SELECT
    trade_date,
    category,
    COUNT(*) as trades_count,
    SUM(pnl_usd) as total_pnl,
    AVG(pnl_usd) as avg_pnl,
    COUNT(CASE WHEN pnl_usd > 0 THEN 1 END) as winning_trades,
    COUNT(CASE WHEN pnl_usd < 0 THEN 1 END) as losing_trades
FROM trades
GROUP BY trade_date, category
ORDER BY trade_date DESC;