-- Создание таблицы записей
CREATE TABLE IF NOT EXISTS records (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    record_date DATE NOT NULL,
    mood INTEGER CHECK (mood BETWEEN 1 AND 5),
    work_hours NUMERIC(4,1) CHECK (work_hours >= 0),
    sleep_hours NUMERIC(4,1) CHECK (sleep_hours >= 0),
    comment TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, record_date)
);

-- Индекс для быстрой выборки по пользователю и дате
CREATE INDEX IF NOT EXISTS idx_user_date ON records(user_id, record_date);
