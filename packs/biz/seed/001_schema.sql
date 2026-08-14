-- 元景.智数 biz 域演示表结构
CREATE TABLE IF NOT EXISTS biz.sub_month (
    month DATE NOT NULL,
    region TEXT NOT NULL,
    sub_cnt INTEGER NOT NULL,
    arpu NUMERIC(10, 2) NOT NULL,
    revenue NUMERIC(14, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS biz.channel_day (
    day DATE NOT NULL,
    channel TEXT NOT NULL,
    new_users INTEGER NOT NULL
);
