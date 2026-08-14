-- 元景.智数 network 域演示表结构
CREATE TABLE IF NOT EXISTS network.cell_hour (
    hour TIMESTAMP NOT NULL,
    cell_id TEXT NOT NULL,
    traffic_gb NUMERIC(12, 3) NOT NULL,
    avail_rate NUMERIC(6, 4) NOT NULL
);

CREATE TABLE IF NOT EXISTS network.alarm_day (
    day DATE NOT NULL,
    alarm_cnt INTEGER NOT NULL,
    critical_cnt INTEGER NOT NULL
);
