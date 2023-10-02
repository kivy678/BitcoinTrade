# -*- coding:utf-8 -*-

#############################################################################
# create table
query_create_symbol_table = """
CREATE TABLE IF NOT EXISTS binance
(
    symbol              str primary key,
    tick_size           float,
    step_size           float,
    min_lot             float,
    min_noti            float,
    rsi                 float,
    status              str
);
"""

# status 값 목록
"""
BUY_ORDER_MONITOR           = 매수 조건이 이루어지기 위한 모니터링
SELL_ORDER_MONITOR          = 매도 조건이 이루어지기 위한 모니터링
"""

query_create_trade_table = """
CREATE TABLE IF NOT EXISTS trade
(
    init_time               str,
    rsi_time                str,
    kline_interval          str,
    rsi_window              int,
    alpha_qty               int,
    trade_qty               int
);
"""

#############################################################################
# insert table
query_insert_symbol_table = """
INSERT OR REPLACE INTO binance
VALUES
(?,?,?,?,?,?,?);
"""

query_insert_trade_base_data = """
INSERT INTO trade
VALUES
(?,?,?,?,?,?);
"""

#############################################################################
# update binance
query_update_rsi = """
UPDATE binance SET
rsi = ?
WHERE symbol = ?
"""

query_update_status = """
UPDATE binance SET
status = ?
WHERE symbol = ?
"""

#############################################################################
# update trade
query_update_init_time = """
UPDATE trade
SET init_time = ?;
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
# get binance
query_get_all_symbol = """
SELECT symbol
FROM binance;
"""

query_get_symbol_info = """
SELECT symbol, rsi, status
FROM binance;
"""

query_get_size_symbol = """
SELECT {0}
FROM binance
WHERE symbol = ?;
"""

#############################################################################
# get trade
query_get_init_time = """
SELECT init_time
FROM trade;
"""

query_get_rsi_set = """
SELECT kline_interval, rsi_window
FROM trade;
"""

query_get_trade_set = """
SELECT alpha_qty, trade_qty
FROM trade;
"""

#############################################################################

