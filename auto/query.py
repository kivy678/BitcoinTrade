# -*- coding:utf-8 -*-

#############################################################################

query_create_symbol_table = """
CREATE TABLE IF NOT EXISTS symbol
(
    symbol              str primary key,
    buy_orderId         int,
    sell_orderId        int,
    tick_size           float,
    step_size           float,
    min_lot             float,
    min_noti            float,
    luctuation_rate     float,
    rsi                 float,
    status              str
);
"""

query_create_trade_table = """
CREATE TABLE IF NOT EXISTS trade
(
    init_time               float,
    sum_noti                float,
    luctuation_rate_time    float,
    rsi_time                float
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

#############################################################################

query_insert_symbol_table = """
INSERT OR REPLACE INTO symbol
VALUES
(?,?,?,?,?,?,?,?,?,?);
"""

query_insert_trade_base_data = """
INSERT INTO trade
VALUES
(?,?,?,?)
"""

#############################################################################

query_init_symbol_table = """
UPDATE symbol SET
buy_orderId = null,
sell_orderId = null,
luctuation_rate = null,
rsi = null,
status = 'WAIT'
"""

query_update_status = """
UPDATE symbol SET
status = ?
WHERE symbol = ?
"""

query_update_buy_orderId = """
UPDATE symbol SET
buy_orderId = ?
WHERE symbol = ?
"""

query_update_sell_orderId = """
UPDATE symbol SET
sell_orderId = ?
WHERE symbol = ?
"""

query_update_luctuation_rate = """
UPDATE symbol
SET luctuation_rate = ?
WHERE symbol = ?
"""

query_update_rsi = """
UPDATE symbol SET
rsi = ?
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
FROM symbol
WHERE status != 'WAIT';
"""

query_get_init_time = """
SELECT init_time
FROM trade;
"""

query_get_symbol_table = """
SELECT symbol
FROM symbol;
"""

query_get_symbol_buy_monitor = """
SELECT symbol
FROM symbol
WHERE status = 'BUY_ORDER_MONITOR';
"""


#############################################################################



