import pytest
from datetime import datetime, timezone

import accounts
from accounts import (
    Account,
    Transaction,
    get_share_price,
    UnknownSymbolError,
    InvalidTransactionError,
    InsufficientFundsError,
    InsufficientSharesError,
)


def test_initial_deposit_sets_baseline_and_transaction():
    acct = Account(account_id="acct-1", owner="Alice", initial_deposit=100.0)
    assert acct.account_id == "acct-1"
    assert acct.owner == "Alice"
    assert acct.get_cash_balance() == 100.0
    assert acct.initial_deposit == 100.0
    assert len(acct.transactions) == 1
    tx = acct.transactions[0]
    assert tx.type == "deposit"
    assert tx.note == "Initial deposit"
    assert tx.cash_delta == 100.0
    assert tx.symbol is None
    assert tx.timestamp.tzinfo is not None

def test_deposit_sets_initial_if_first_and_validations():
    acct = Account(account_id="acct-2")
    tx = acct.deposit(50.0, note="first")
    assert acct.get_cash_balance() == 50.0
    assert acct.initial_deposit == 50.0
    assert tx.type == "deposit"
    assert tx.note == "first"

    # invalid deposit amounts
    with pytest.raises(InvalidTransactionError):
        acct.deposit(0)
    with pytest.raises(InvalidTransactionError):
        acct.deposit(-10)

def test_withdraw_success_and_insufficient():
    acct = Account(account_id="acct-3")
    acct.deposit(200.0)
    tx = acct.withdraw(75.0, note="atm")
    assert acct.get_cash_balance() == pytest.approx(125.0)
    assert tx.type == "withdraw"
    assert tx.cash_delta == -75.0

    with pytest.raises(InsufficientFundsError):
        acct.withdraw(1000.0)

def test_buy_sell_flow_and_validations():
    acct = Account(account_id="acct-4")
    acct.deposit(1000.0)

    # Successful buy
    tx_buy = acct.buy("AAPL", 2)  # default price 150 -> cost 300
    assert acct.get_cash_balance() == pytest.approx(700.0)
    assert acct.get_holdings()["AAPL"] == 2
    assert tx_buy.type == "buy"
    assert tx_buy.symbol == "AAPL"
    assert tx_buy.quantity == 2

    # Selling one share
    tx_sell = acct.sell("AAPL", 1)
    # sell price default 150 -> proceeds 150
    assert acct.get_cash_balance() == pytest.approx(850.0)
    assert acct.get_holdings()["AAPL"] == 1
    assert tx_sell.type == "sell"
    assert tx_sell.cash_delta == pytest.approx(150.0)

    # Selling too many shares
    with pytest.raises(InsufficientSharesError):
        acct.sell("AAPL", 10)

    # Buy with insufficient funds
    with pytest.raises(InsufficientFundsError):
        acct.buy("TSLA", 10000)

    # Invalid quantities
    with pytest.raises(InvalidTransactionError):
        acct.buy("AAPL", 0)
    with pytest.raises(InvalidTransactionError):
        acct.sell("AAPL", 0)

def test_get_portfolio_value_and_total_balance_and_profit_loss():
    acct = Account(account_id="acct-5")
    acct.deposit(1000.0)
    acct.buy("AAPL", 2)   # 2 * 150 = 300
    acct.buy("TSLA", 1)   # 1 * 700 = 700

    # default provider
    pv = acct.get_portfolio_value()
    assert pv == pytest.approx(300.0 + 700.0)

    total = acct.get_total_balance()
    assert total == pytest.approx(acct.get_cash_balance() + pv)

    pl = acct.get_profit_loss()
    assert pl == pytest.approx(total - acct.initial_deposit)

    # custom provider
    def fake_provider(symbol: str) -> float:
        if symbol == "AAPL":
            return 200.0
        if symbol == "TSLA":
            return 600.0
        raise UnknownSymbolError(symbol)

    pv2 = acct.get_portfolio_value(price_provider=fake_provider)
    assert pv2 == pytest.approx(2 * 200.0 + 1 * 600.0)

def test_list_transactions_filters_and_get_transaction():
    acct = Account(account_id="acct-6")
    t1 = acct.deposit(100.0)
    t2 = acct.buy("AAPL", 1)
    t3 = acct.withdraw(25.0)
    t4 = acct.sell("AAPL", 1)

    # by type
    buys = acct.list_transactions(type_filter="buy")
    assert len(buys) == 1 and buys[0].tx_id == t2.tx_id

    # by symbol
    aapl_txs = acct.list_transactions(symbol_filter="AAPL")
    # buy and sell for AAPL
    assert {tx.tx_id for tx in aapl_txs} == {t2.tx_id, t4.tx_id}

    # by start/end timestamps
    start = t2.timestamp
    end = t3.timestamp
    ranged = acct.list_transactions(start=start, end=end)
    # should include t2 and t3 (t1 before start, t4 after end)
    assert {tx.tx_id for tx in ranged} == {t2.tx_id, t3.tx_id}

    # invalid range
    with pytest.raises(InvalidTransactionError):
        acct.list_transactions(start=t4.timestamp, end=t1.timestamp)

    # get_transaction
    assert acct.get_transaction(t2.tx_id) is not None
    assert acct.get_transaction("non-existent") is None

def test_get_holdings_is_copy_and_statement_contents():
    acct = Account(account_id="acct-7", owner="Bob")
    acct.deposit(500.0)
    acct.buy("AAPL", 1)
    holdings = acct.get_holdings()
    holdings["AAPL"] = 999
    # original should not be mutated
    assert acct.get_holdings()["AAPL"] == 1

    stmt = acct.statement()
    assert stmt["account_id"] == "acct-7"
    assert stmt["owner"] == "Bob"
    assert stmt["cash_balance"] == acct.get_cash_balance()
    assert isinstance(stmt["portfolio_value"], float)
    assert stmt["number_of_transactions"] == len(acct.transactions)

def test_unknown_symbol_price_provider_and_exceptions_from_buy():
    acct = Account(account_id="acct-8")
    acct.deposit(1000.0)
    with pytest.raises(UnknownSymbolError):
        # buying a symbol not known to get_share_price should raise
        acct.buy("UNKNOWN", 1)

    # directly test get_share_price
    with pytest.raises(UnknownSymbolError):
        get_share_price("XXX")

def test_transactions_have_unique_ids_and_timezone():
    acct = Account(account_id="acct-9")
    txs = []
    txs.append(acct.deposit(10.0))
    txs.append(acct.deposit(20.0))
    txs.append(acct.withdraw(5.0))

    ids = {t.tx_id for t in txs}
    assert len(ids) == len(txs)

    for t in txs:
        assert t.timestamp.tzinfo is not None
        # timestamps should be in UTC tzinfo
        assert t.timestamp.tzinfo.utcoffset(t.timestamp) == timezone.utc.utcoffset(t.timestamp)