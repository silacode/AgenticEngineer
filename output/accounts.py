from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional, Dict, List, Any, Callable
import uuid
import threading

# Module-level exceptions
class AccountError(Exception):
    """Base class for account-related errors."""
    pass

class InsufficientFundsError(AccountError):
    """Raised when an operation would lead to negative cash balance."""
    pass

class InsufficientSharesError(AccountError):
    """Raised when attempting to sell more shares than held."""
    pass

class InvalidTransactionError(AccountError):
    """Raised for invalid transaction parameters."""
    pass

class UnknownSymbolError(AccountError):
    """Raised when an unknown stock symbol is requested."""
    pass

# Test price provider
def get_share_price(symbol: str) -> float:
    """Return a fixed price for supported symbols; raise UnknownSymbolError otherwise."""
    prices = {
        "AAPL": 150.00,
        "TSLA": 700.00,
        "GOOGL": 2800.00,
    }
    try:
        return prices[symbol]
    except KeyError:
        raise UnknownSymbolError(f"Unknown symbol: {symbol}")

@dataclass(frozen=True)
class Transaction:
    tx_id: str
    timestamp: datetime
    type: str  # 'deposit', 'withdraw', 'buy', 'sell'
    symbol: Optional[str]
    quantity: Optional[int]
    price: Optional[float]
    cash_delta: float
    holdings_delta: Dict[str, int]
    note: Optional[str]

class Account:
    def __init__(self, account_id: str, owner: Optional[str] = None, initial_deposit: float = 0.0) -> None:
        if initial_deposit < 0:
            raise InvalidTransactionError("initial_deposit must be >= 0")

        self.account_id: str = account_id
        self.owner: Optional[str] = owner
        self.initial_deposit: float = 0.0  # will be set to first deposit if provided
        self.cash_balance: float = 0.0
        self.holdings: Dict[str, int] = {}
        self.transactions: List[Transaction] = []

        # Optional lock for thread-safety
        self._lock = threading.Lock()

        if initial_deposit > 0:
            # record as first deposit and set initial_deposit baseline
            tx = self._record_transaction(
                type="deposit",
                cash_delta=initial_deposit,
                holdings_delta={},
                symbol=None,
                quantity=None,
                price=None,
                note="Initial deposit"
            )
            self.cash_balance += initial_deposit
            self.initial_deposit = initial_deposit

    # Public methods
    def deposit(self, amount: float, note: Optional[str] = None) -> Transaction:
        self._validate_positive_amount(amount)
        with self._lock:
            self.cash_balance += amount
            tx = self._record_transaction(
                type="deposit",
                cash_delta=amount,
                holdings_delta={},
                symbol=None,
                quantity=None,
                price=None,
                note=note,
            )
            # If initial_deposit was not set (==0.0) and this is the first deposit, set baseline
            if self.initial_deposit == 0.0 and self._count_deposits() == 1:
                self.initial_deposit = amount
            return tx

    def withdraw(self, amount: float, note: Optional[str] = None) -> Transaction:
        self._validate_positive_amount(amount)
        with self._lock:
            if self.cash_balance - amount < 0:
                raise InsufficientFundsError("Insufficient cash to withdraw the requested amount")
            self.cash_balance -= amount
            tx = self._record_transaction(
                type="withdraw",
                cash_delta=-amount,
                holdings_delta={},
                symbol=None,
                quantity=None,
                price=None,
                note=note,
            )
            return tx

    def buy(self, symbol: str, quantity: int, price: Optional[float] = None, note: Optional[str] = None) -> Transaction:
        if quantity <= 0:
            raise InvalidTransactionError("quantity must be > 0")
        with self._lock:
            exec_price = price if price is not None else get_share_price(symbol)
            if exec_price is None or exec_price < 0:
                raise InvalidTransactionError("Invalid price provided")
            cost = exec_price * quantity
            if self.cash_balance - cost < 0:
                raise InsufficientFundsError("Insufficient cash to execute buy order")
            self.cash_balance -= cost
            self.holdings[symbol] = self.holdings.get(symbol, 0) + quantity
            holdings_delta = {symbol: quantity}
            tx = self._record_transaction(
                type="buy",
                cash_delta=-cost,
                holdings_delta=holdings_delta,
                symbol=symbol,
                quantity=quantity,
                price=exec_price,
                note=note,
            )
            return tx

    def sell(self, symbol: str, quantity: int, price: Optional[float] = None, note: Optional[str] = None) -> Transaction:
        if quantity <= 0:
            raise InvalidTransactionError("quantity must be > 0")
        with self._lock:
            current_shares = self.holdings.get(symbol, 0)
            if current_shares - quantity < 0:
                raise InsufficientSharesError("Insufficient shares to execute sell order")
            exec_price = price if price is not None else get_share_price(symbol)
            if exec_price is None or exec_price < 0:
                raise InvalidTransactionError("Invalid price provided")
            proceeds = exec_price * quantity
            self.cash_balance += proceeds
            new_shares = current_shares - quantity
            if new_shares == 0:
                self.holdings.pop(symbol, None)
            else:
                self.holdings[symbol] = new_shares
            holdings_delta = {symbol: -quantity}
            tx = self._record_transaction(
                type="sell",
                cash_delta=proceeds,
                holdings_delta=holdings_delta,
                symbol=symbol,
                quantity=quantity,
                price=exec_price,
                note=note,
            )
            return tx

    def get_holdings(self) -> Dict[str, int]:
        # return a shallow copy to prevent external mutation
        return dict(self.holdings)

    def get_cash_balance(self) -> float:
        return float(self.cash_balance)

    def get_portfolio_value(self, price_provider: Optional[Callable[[str], float]] = None) -> float:
        provider = price_provider if price_provider is not None else get_share_price
        total = 0.0
        for symbol, qty in self.holdings.items():
            price = provider(symbol)
            total += price * qty
        return total

    def get_total_balance(self, price_provider: Optional[Callable[[str], float]] = None) -> float:
        return self.cash_balance + self.get_portfolio_value(price_provider)

    def get_profit_loss(self, price_provider: Optional[Callable[[str], float]] = None) -> float:
        return self.get_total_balance(price_provider) - self.initial_deposit

    def list_transactions(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        type_filter: Optional[str] = None,
        symbol_filter: Optional[str] = None,
    ) -> List[Transaction]:
        if start is not None and end is not None and start > end:
            raise InvalidTransactionError("start must be <= end")
        result: List[Transaction] = []
        for tx in self.transactions:
            if start is not None and tx.timestamp < start:
                continue
            if end is not None and tx.timestamp > end:
                continue
            if type_filter is not None and tx.type != type_filter:
                continue
            if symbol_filter is not None:
                if tx.symbol != symbol_filter:
                    continue
            result.append(tx)
        return list(result)

    def get_transaction(self, tx_id: str) -> Optional[Transaction]:
        for tx in self.transactions:
            if tx.tx_id == tx_id:
                return tx
        return None

    def statement(self, price_provider: Optional[Callable[[str], float]] = None) -> Dict[str, Any]:
        pv = self.get_portfolio_value(price_provider)
        total = self.cash_balance + pv
        pl = total - self.initial_deposit
        return {
            "account_id": self.account_id,
            "owner": self.owner,
            "cash_balance": float(self.cash_balance),
            "holdings": self.get_holdings(),
            "portfolio_value": pv,
            "total_balance": total,
            "profit_loss": pl,
            "number_of_transactions": len(self.transactions),
        }

    # Internal helpers
    def _record_transaction(
        self,
        type: str,
        cash_delta: float,
        holdings_delta: Dict[str, int],
        symbol: Optional[str] = None,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        note: Optional[str] = None,
    ) -> Transaction:
        tx = Transaction(
            tx_id=str(uuid.uuid4()),
            timestamp=self._current_time(),
            type=type,
            symbol=symbol,
            quantity=quantity,
            price=price,
            cash_delta=cash_delta,
            holdings_delta=dict(holdings_delta),
            note=note,
        )
        self.transactions.append(tx)
        return tx

    def _current_time(self) -> datetime:
        # timezone-aware UTC timestamp
        return datetime.now(timezone.utc)

    def _validate_positive_amount(self, amount: float) -> None:
        if amount <= 0:
            raise InvalidTransactionError("amount must be > 0")

    def _count_deposits(self) -> int:
        return sum(1 for tx in self.transactions if tx.type == "deposit")

# If this module is run directly, perform a small sanity demonstration
if __name__ == "__main__":
    acct = Account(account_id="acct-1", owner="Alice", initial_deposit=10000.0)
    print('Initial statement:', acct.statement())
    acct.buy('AAPL', 10)
    acct.buy('TSLA', 2)
    acct.sell('AAPL', 5)
    acct.withdraw(500)
    print('Final statement:', acct.statement())
    print('Transactions:')
    for t in acct.list_transactions():
        print(t)