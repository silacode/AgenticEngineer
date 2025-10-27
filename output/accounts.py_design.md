# accounts.py — Design (detailed)

This design describes a single self-contained Python module named `accounts.py`. It defines an `Account` class that implements a simple trading-simulation account management system, a test `get_share_price(symbol)` implementation, transaction data structures, and custom exceptions. The design includes all function/method signatures, internal data structures, invariants, and behavior required by the requirements.

All state is in-memory within the Account instance. The module is designed so it can be implemented directly from this specification and unit-tested or used to build a small UI.

---

## Module overview

- Module name: `accounts.py`
- Main class: `Account`
- Supporting data structure: `Transaction` (dataclass)
- Module-level function: `get_share_price(symbol: str) -> float` (test implementation)
- Custom exceptions:
  - `AccountError` (base)
  - `InsufficientFundsError`
  - `InsufficientSharesError`
  - `InvalidTransactionError`
  - `UnknownSymbolError`

---

## Data model

1. Transaction dataclass (immutable record of each action):
   - Purpose: store every deposit, withdrawal, buy, sell with timestamp and the effect on cash and holdings.
   - Fields:
     - `tx_id: str` — unique transaction id (e.g., UUID string)
     - `timestamp: datetime` — UTC timestamp of transaction
     - `type: str` — one of `deposit`, `withdraw`, `buy`, `sell`
     - `symbol: Optional[str]` — stock symbol for `buy`/`sell`, else None
     - `quantity: Optional[int]` — number of shares for `buy`/`sell`, else None
     - `price: Optional[float]` — price per share at execution for `buy`/`sell`, else None
     - `cash_delta: float` — positive for deposit/sell, negative for withdraw/buy
     - `holdings_delta: Dict[str, int]` — change of holdings by symbol (empty for deposit/withdraw)
     - `note: Optional[str]` — optional free-text note
   - This dataclass is used in the transaction ledger and returned to callers.

2. Account runtime state:
   - `account_id: str`
   - `owner: Optional[str]`
   - `initial_deposit: float` — sum of all deposits up to a configurable initial point; design defaults to the first deposit if provided at creation, otherwise zero; used as the base for P/L calculation
   - `cash_balance: float` — current available cash (float)
   - `holdings: Dict[str, int]` — mapping: symbol -> integer share count (>= 0)
   - `transactions: List[Transaction]` — chronological ledger (append-only)
   - (Optional) `lock` — threading.Lock if thread-safety is desired

Notes:
- All money/currency values are floats in this design for simplicity. In production, Decimal is recommended to avoid floating-point rounding issues.
- Quantities are ints (no fractional shares in this simple design).

---

## Exceptions

Signatures:

- class AccountError(Exception)
- class InsufficientFundsError(AccountError)
- class InsufficientSharesError(AccountError)
- class InvalidTransactionError(AccountError)
- class UnknownSymbolError(AccountError)

Behavior:
- InsufficientFundsError raised when a withdrawal or buy would leave cash_balance < 0.
- InsufficientSharesError raised when a sell would reduce holdings[symbol] < 0.
- InvalidTransactionError for invalid input (e.g., negative deposit, zero quantity).
- UnknownSymbolError raised if a symbol is not supported by `get_share_price` (test implementation supports AAPL, TSLA, GOOGL).

---

## Module-level helper: get_share_price

Signature:

- get_share_price(symbol: str) -> float

Description:

- Returns the current price for the requested symbol.
- Test implementation returns fixed prices:
  - "AAPL" -> 150.00
  - "TSLA" -> 700.00
  - "GOOGL" -> 2800.00
- If an unknown symbol is requested, it raises `UnknownSymbolError`.
- The function may be replaced or mocked in tests to return dynamic prices.

---

## Account class

Class signature:

- class Account:
    - def __init__(self, account_id: str, owner: Optional[str] = None, initial_deposit: float = 0.0) -> None

Constructor behavior:
- Creates an account with provided `account_id` and optional `owner`.
- If `initial_deposit > 0`, it is applied as the first deposit transaction:
  - increments cash_balance
  - appends a `deposit` transaction to `transactions`
  - sets `initial_deposit` field to provided amount (used for P/L baseline)
- If `initial_deposit == 0`, `initial_deposit` field defaults to 0.0.
- Initializes holdings to empty dict, cash_balance accordingly.
- Validates input (initial_deposit >= 0), else raises `InvalidTransactionError`.

Public methods (all method signatures included):

1. deposit

Signature:
- def deposit(self, amount: float, note: Optional[str] = None) -> Transaction

Behavior:
- Validates amount > 0 else raise `InvalidTransactionError`.
- Increases `cash_balance` by `amount`.
- Records a `deposit` Transaction with `cash_delta = +amount`.
- If this is the very first deposit and `initial_deposit` was 0.0 in constructor, set `initial_deposit` to sum of deposits up to now (or explicitly to the first deposit amount depending on chosen baseline; design chooses to set `initial_deposit` to first deposit if constructor didn't receive a positive initial_deposit).
- Returns the Transaction object.

2. withdraw

Signature:
- def withdraw(self, amount: float, note: Optional[str] = None) -> Transaction

Behavior:
- Validates amount > 0 else `InvalidTransactionError`.
- Checks `cash_balance - amount >= 0`, else raise `InsufficientFundsError`.
- Decreases `cash_balance` by `amount`.
- Records a `withdraw` Transaction with `cash_delta = -amount`.
- Returns the Transaction object.

3. buy

Signature:
- def buy(self, symbol: str, quantity: int, price: Optional[float] = None, note: Optional[str] = None) -> Transaction

Behavior:
- Validates quantity > 0 else `InvalidTransactionError`.
- Resolves `price`:
  - If `price` is provided, use it.
  - Else call `get_share_price(symbol)` to obtain current price (may raise `UnknownSymbolError`).
- Calculates `cost = price * quantity`.
- Checks `cash_balance - cost >= 0`, else raise `InsufficientFundsError`.
- Subtracts `cost` from `cash_balance`.
- Increments holdings[symbol] by `quantity` (creates key if needed).
- Records a `buy` Transaction:
  - `symbol`, `quantity`, `price`, `cash_delta = -cost`, `holdings_delta = {symbol: +quantity}`.
- Returns the Transaction object.

Notes:
- Implementation detail: If `price` provided differs from `get_share_price`, it is allowed (useful for backtesting/historical trades); but validation may assert `price >= 0` and allow injection.

4. sell

Signature:
- def sell(self, symbol: str, quantity: int, price: Optional[float] = None, note: Optional[str] = None) -> Transaction

Behavior:
- Validates quantity > 0 else `InvalidTransactionError`.
- Confirms holdings.get(symbol, 0) - quantity >= 0, else raise `InsufficientSharesError`.
- Resolves `price` same as buy (optional param or call `get_share_price`).
- Calculates `proceeds = price * quantity`.
- Adds `proceeds` to `cash_balance`.
- Decrements holdings[symbol] by `quantity`. If holdings[symbol] becomes 0, remove the symbol from holdings.
- Records a `sell` Transaction with `cash_delta = +proceeds` and `holdings_delta = {symbol: -quantity}`.
- Returns the Transaction object.

5. get_holdings

Signature:
- def get_holdings(self) -> Dict[str, int]

Behavior:
- Returns a copy of the holdings dictionary (symbol -> quantity).
- The method returns a shallow copy to prevent external mutation.

6. get_cash_balance

Signature:
- def get_cash_balance(self) -> float

Behavior:
- Returns current `cash_balance`.

7. get_portfolio_value

Signature:
- def get_portfolio_value(self, price_provider: Optional[Callable[[str], float]] = None) -> float

Behavior:
- Calculates market value of holdings using prices from:
  - `price_provider` callable if provided (signature price_provider(symbol) -> float),
  - else module-level `get_share_price`.
- For each symbol in holdings, multiply quantity by price and sum.
- If price lookup for any symbol raises `UnknownSymbolError`, bubble up or optionally treat missing as zero (design: raise `UnknownSymbolError` to signal caller).
- Returns total market value (float).

8. get_total_balance

Signature:
- def get_total_balance(self, price_provider: Optional[Callable[[str], float]] = None) -> float

Behavior:
- Returns `cash_balance + get_portfolio_value(price_provider)`.

9. get_profit_loss

Signature:
- def get_profit_loss(self, price_provider: Optional[Callable[[str], float]] = None) -> float

Behavior:
- Computes profit/loss relative to `initial_deposit`.
- P/L = get_total_balance(price_provider) - initial_deposit
- Returns a float: positive indicates profit, negative indicates loss.
- If initial_deposit == 0, P/L is simply the current total balance (and caller should be aware).

10. list_transactions

Signature:
- def list_transactions(self, start: Optional[datetime] = None, end: Optional[datetime] = None, type_filter: Optional[str] = None, symbol_filter: Optional[str] = None) -> List[Transaction]

Behavior:
- Returns a list of Transaction objects from the ledger filtered by optional time range and optional type (`deposit`, `withdraw`, `buy`, `sell`) and optional symbol.
- Returns a shallow copy of the matching transactions ordered chronologically ascending.
- Input validation: if `start` > `end`, raise `InvalidTransactionError`.

11. get_transaction

Signature:
- def get_transaction(self, tx_id: str) -> Optional[Transaction]

Behavior:
- Returns the transaction with the matching `tx_id` if found, else None.

12. summary / statement (convenience)

Signature:
- def statement(self, price_provider: Optional[Callable[[str], float]] = None) -> Dict[str, Any]

Behavior:
- Returns a structured summary dictionary containing:
  - account_id, owner
  - cash_balance
  - holdings (copy)
  - portfolio_value
  - total_balance
  - profit_loss
  - number_of_transactions
- Useful for UI display or tests.

---

## Private/internal helper methods (signatures + description)

These methods are intended to be implementation helpers inside the class (prefixed with underscore).

1. _record_transaction

Signature:
- def _record_transaction(self, type: str, cash_delta: float, holdings_delta: Dict[str, int], symbol: Optional[str] = None, quantity: Optional[int] = None, price: Optional[float] = None, note: Optional[str] = None) -> Transaction

Behavior:
- Creates a Transaction instance with a new UUID and current UTC timestamp.
- Appends to `self.transactions`.
- Returns the Transaction.

2. _current_time

Signature:
- def _current_time(self) -> datetime

Behavior:
- Returns datetime.utcnow() (or datetime.now(timezone.utc) for timezone-aware timestamps).
- Centralizes timestamp generation for easier testing (can be overridden or monkeypatched).

3. _validate_positive_amount

Signature:
- def _validate_positive_amount(self, amount: float) -> None

Behavior:
- Raises `InvalidTransactionError` if amount <= 0.

---

## Concurrency considerations

- The in-memory design is not thread-safe by default.
- Optionally include a `threading.Lock` instance on the Account (created in __init__) and wrap state-changing operations (deposit, withdraw, buy, sell) with lock acquisition/release.
- Method signatures remain unchanged; thread-safety is an implementation detail.

---

## Edge cases and invariants

- Cash balance invariant: cash_balance is always >= 0.
- Holdings invariant: holdings[symbol] is always an integer >= 0; symbols with zero shares are removed.
- Transaction ledger: append-only chronological list.
- Buy validation: must have enough cash to pay for cost at the price used.
- Sell validation: must have enough shares of the symbol.
- Withdraw validation: cannot withdraw more than cash_balance.

---

## Example usage (pseudocode)

Note: This is design-level pseudocode for sample flows; not a required implementation.

- Create account with initial deposit:
  account = Account(account_id="acct-123", owner="Alice", initial_deposit=10000.0)
  -> creates a deposit transaction and sets cash_balance = 10000.0 and initial_deposit = 10000.0.

- Buy shares:
  tx = account.buy("AAPL", quantity=10)
  -> `get_share_price("AAPL")` returns 150.0; cost = 1500.0; cash_balance becomes 8500.0; holdings["AAPL"] = 10.

- Sell shares:
  tx = account.sell("AAPL", quantity=5)
  -> proceeds = 5 * price; cash_balance increases, holdings updated.

- Withdraw:
  tx = account.withdraw(1000.0)
  -> cash_balance decreases if funds available.

- Get portfolio value & P/L:
  pv = account.get_portfolio_value()  # sum(quantity*price)
  total = account.get_total_balance()
  pl = account.get_profit_loss()

- List transactions:
  ledger = account.list_transactions()

---

## Testing notes

- The module-level `get_share_price` returns deterministic values for AAPL/TSLA/GOOGL to enable predictable tests.
- Write unit tests covering:
  - deposits and initial_deposit behavior
  - attempting to withdraw more than cash_balance raises InsufficientFundsError
  - attempting to buy more than cash allows raises InsufficientFundsError
  - attempting to sell more shares than held raises InsufficientSharesError
  - correct ledger entries: cash_delta and holdings_delta correctness
  - portfolio value and profit/loss calculations with given prices
  - filtering in list_transactions by type, symbol, and date range
- Consider tests that pass a mock price_provider to get_portfolio_value to simulate price changes and verify P/L updates.

---

## Full list of function and method signatures (summary)

Module-level:
- def get_share_price(symbol: str) -> float

Exceptions:
- class AccountError(Exception)
- class InsufficientFundsError(AccountError)
- class InsufficientSharesError(AccountError)
- class InvalidTransactionError(AccountError)
- class UnknownSymbolError(AccountError)

Transaction dataclass:
- @dataclass(frozen=True)
  class Transaction:
    tx_id: str
    timestamp: datetime
    type: str
    symbol: Optional[str]
    quantity: Optional[int]
    price: Optional[float]
    cash_delta: float
    holdings_delta: Dict[str, int]
    note: Optional[str]

Account class:
- class Account:
    - def __init__(self, account_id: str, owner: Optional[str] = None, initial_deposit: float = 0.0) -> None
    - def deposit(self, amount: float, note: Optional[str] = None) -> Transaction
    - def withdraw(self, amount: float, note: Optional[str] = None) -> Transaction
    - def buy(self, symbol: str, quantity: int, price: Optional[float] = None, note: Optional[str] = None) -> Transaction
    - def sell(self, symbol: str, quantity: int, price: Optional[float] = None, note: Optional[str] = None) -> Transaction
    - def get_holdings(self) -> Dict[str, int]
    - def get_cash_balance(self) -> float
    - def get_portfolio_value(self, price_provider: Optional[Callable[[str], float]] = None) -> float
    - def get_total_balance(self, price_provider: Optional[Callable[[str], float]] = None) -> float
    - def get_profit_loss(self, price_provider: Optional[Callable[[str], float]] = None) -> float
    - def list_transactions(self, start: Optional[datetime] = None, end: Optional[datetime] = None, type_filter: Optional[str] = None, symbol_filter: Optional[str] = None) -> List[Transaction]
    - def get_transaction(self, tx_id: str) -> Optional[Transaction]
    - def statement(self, price_provider: Optional[Callable[[str], float]] = None) -> Dict[str, Any]

Private helpers:
- def _record_transaction(self, type: str, cash_delta: float, holdings_delta: Dict[str, int], symbol: Optional[str] = None, quantity: Optional[int] = None, price: Optional[float] = None, note: Optional[str] = None) -> Transaction
- def _current_time(self) -> datetime
- def _validate_positive_amount(self, amount: float) -> None

---

This design should be sufficient for an engineer to implement the `accounts.py` module in a single file, write unit tests against the deterministic `get_share_price`, and build a minimal UI or CLI on top of it.