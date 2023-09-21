# -*- coding:utf-8 -*-

#############################################################################

query_create_symbol_table = """
CREATE TABLE IF NOT EXISTS binance
(
    symbol              str primary key,
    buy_orderId         int,
    sell_orderId        int,
    order_wait_time     int,
    tick_size           float,
    step_size           float,
    min_lot             float,
    min_noti            float,
    luctuation_rate     float,
    rsi                 float,
    status              str
);
"""

# status 값 목록
"""
WAIT                        = 선정되기 전
BUY_ORDER_MONITOR           = 매수 조건이 이루어지기 위한 모니터링
BUY_ORDER_EXECUTE_WAIT      = 매수 주문 체결 대기
SELL_ORDER_MONITOR          = 매도 조건이 이루어지기 위한 모니터링
SELL_ORDER_EXECUTE_WAIT     = 매도 주문 체결 대기
"""

query_create_trade_table = """
CREATE TABLE IF NOT EXISTS trade
(
    init_time               str,
    sum_noti                float,
    luctuation_rate_time    str,
    rsi_time                str
);
"""

query_create_rate_table = """
CREATE TABLE IF NOT EXISTS rate
(
    time                    str primary key,
    symbol                  str,
    qty                     float,
    quoteQty                float,
    price                   float,
    commission              float,
    buyer                   str
);
"""

query_create_total_rate_table = """
CREATE TABLE IF NOT EXISTS total_rate
(
    time                    str,
    symbol                  str,
    return_rate             float,

    CONSTRAINT total_rate_time_symbol UNIQUE (time, symbol)
);
"""

# interval 값이 분이고 intervalNum 5이면 5분을 뜻함
# REQUEST_WEIGHT 는 가중치인데 쿼리마다 가중치 값이 다르다.
# RAW_REQUESTS 는 순수 쿼리 수량을 뜻함
query_create_api_limit_table = """
CREATE TABLE IF NOT EXISTS api_limit
(
    api_interval             int,
    intervalNum              int,
    api_limit                int,
    rateLimitType            str
);
"""

#############################################################################

query_insert_symbol_table = """
INSERT OR REPLACE INTO binance
VALUES
(?,?,?,?,?,?,?,?,?,?,?);
"""

query_insert_trade_base_data = """
INSERT INTO trade
VALUES
(?,?,?,?);
"""

query_insert_rate_table = """
INSERT OR REPLACE INTO rate
VALUES
(?,?,?,?,?,?,?);
"""

query_insert_total_rate_table = """
INSERT OR REPLACE INTO total_rate
VALUES
(?,?,?);
"""

query_insert_api_limit_table = """
INSERT INTO api_limit
VALUES
(?,?,?,?);
"""


#############################################################################

query_init_symbol_table = """
UPDATE binance SET
buy_orderId = null,
sell_orderId = null,
luctuation_rate = null,
rsi = null,
status = 'WAIT'
"""

query_update_status = """
UPDATE binance SET
status = ?
WHERE symbol = ?
"""

query_update_order_id = """
UPDATE binance SET
buy_orderId = ?,
sell_orderId = ?
WHERE symbol = ?
"""

query_update_luctuation_rate = """
UPDATE binance
SET luctuation_rate = ?
WHERE symbol = ?
"""

query_update_rsi = """
UPDATE binance SET
rsi = ?
WHERE symbol = ?
"""

query_update_order_wait_time = """
UPDATE binance SET
order_wait_time = ?
WHERE symbol = ?
"""

query_update_init_time = """
UPDATE trade
SET init_time = ?;
"""

query_update_sum_noti = """
UPDATE trade
SET sum_noti = ?;
"""

query_update_rsi_time = """
UPDATE trade
SET rsi_time = ?;
"""

query_update_luctuation_rate_time = """
UPDATE trade
SET luctuation_rate_time = ?;
"""

#############################################################################

query_get_symbol_info = """
SELECT symbol, buy_orderId, sell_orderId, rsi, status
FROM binance
WHERE status != 'WAIT';
"""

query_get_init_time = """
SELECT init_time
FROM trade;
"""

query_get_symbol_table = """
SELECT symbol
FROM binance
WHERE status = 'WAIT';
"""

query_get_symbol_buy_monitor = """
SELECT symbol
FROM binance
WHERE status = 'BUY_ORDER_MONITOR';
"""

query_get_size_symbol = """
SELECT {0}
FROM binance
WHERE symbol = ?;
"""

query_get_symbol_sell_monitor = """
SELECT symbol
FROM binance
WHERE status = 'SELL_ORDER_MONITOR';
"""

query_get_all_symbol = """
SELECT symbol
FROM binance;
"""

query_get_order_wait_time = """
SELECT order_wait_time
FROM binance
WHERE symbol = ?;
"""

query_get_order_wait_time_count = """
SELECT symbol
FROM binance
WHERE order_wait_time > 0;
"""

query_get_total_rate = """
SELECT *
FROM total_rate;
"""

#############################################################################



