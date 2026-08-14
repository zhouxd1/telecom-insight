-- 元景.智数 cs 域演示表结构
CREATE TABLE IF NOT EXISTS cs.ticket_day (
    day DATE NOT NULL,
    ticket_type TEXT NOT NULL,
    ticket_cnt INTEGER NOT NULL,
    csat NUMERIC(4, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS cs.repeat_month (
    month DATE NOT NULL,
    repeat_cnt INTEGER NOT NULL
);
