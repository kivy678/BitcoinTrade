# -*- coding:utf-8 -*-

#############################################################################
# create table
query_create_symbol_table = """
CREATE TABLE IF NOT EXISTS upbit
(
    symbol              str primary key,
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
    trade_qty               int
);
"""

#############################################################################
# insert table
query_insert_symbol_table = """
INSERT OR REPLACE INTO upbit
VALUES
(?,?,?,?);
"""

query_insert_trade_base_data = """
INSERT INTO trade
VALUES
(?,?,?,?,?);
"""

#############################################################################
# update upbit
query_update_rsi = """
UPDATE upbit SET
rsi = ?
WHERE symbol = ?
"""

query_update_status = """
UPDATE upbit SET
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

#############################################################################
# get upbit
query_get_all_symbol = """
SELECT symbol
FROM upbit;
"""

query_get_symbol_info = """
SELECT symbol, rsi, status
FROM upbit;
"""

query_get_size_symbol = """
SELECT min_noti
FROM upbit
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
SELECT trade_qty
FROM trade;
"""

#############################################################################

