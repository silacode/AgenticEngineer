from datetime import timezone
import uuid
import traceback

import gradio as gr

from accounts import Account, get_share_price, AccountError, InsufficientFundsError, InsufficientSharesError, InvalidTransactionError, UnknownSymbolError

# Single global account for this simple demo
acct: Account | None = None

SUPPORTED_SYMBOLS = ["AAPL", "TSLA", "GOOGL"]


def format_currency(x: float) -> str:
    return f"${x:,.2f}"


def statement_text(account: Account) -> str:
    stmt = account.statement(price_provider=get_share_price)
    lines = []
    lines.append(f"Account ID: {stmt['account_id']}")
    lines.append(f"Owner: {stmt['owner']}")
    lines.append(f"Cash balance: {format_currency(stmt['cash_balance'])}")
    lines.append("Holdings:")
    holdings = stmt["holdings"]
    if not holdings:
        lines.append("  (no holdings)")
    else:
        for sym, qty in holdings.items():
            price = get_share_price(sym)
            value = price * qty
            lines.append(f"  {sym}: {qty} shares @ {format_currency(price)} = {format_currency(value)}")
    lines.append(f"Portfolio value: {format_currency(stmt['portfolio_value'])}")
    lines.append(f"Total balance: {format_currency(stmt['total_balance'])}")
    pl = stmt["profit_loss"]
    pl_str = f"{format_currency(pl)}"
    if pl > 0:
        pl_str += " (profit)"
    elif pl < 0:
        pl_str += " (loss)"
    else:
        pl_str += " (breakeven)"
    lines.append(f"Profit / Loss: {pl_str}")
    lines.append(f"Number of transactions: {stmt['number_of_transactions']}")
    return "\n".join(lines)


def holdings_text(account: Account) -> str:
    h = account.get_holdings()
    if not h:
        return "(no holdings)"
    lines = []
    for sym, qty in h.items():
        price = get_share_price(sym)
        lines.append(f"{sym}: {qty} shares  |  price: {format_currency(price)}  |  value: {format_currency(price * qty)}")
    return "\n".join(lines)


def transactions_text(account: Account, limit: int = 50) -> str:
    txs = account.list_transactions()
    if not txs:
        return "(no transactions)"
    # Show most recent first
    txs_to_show = list(reversed(txs))[:limit]
    lines = []
    for tx in txs_to_show:
        ts = tx.timestamp.astimezone(timezone.utc).isoformat()
        if tx.type in ("deposit", "withdraw"):
            lines.append(f"{ts} | {tx.type.upper():7} | cash Δ {format_currency(tx.cash_delta)} | note: {tx.note or '-'} | id: {tx.tx_id}")
        else:
            # buy or sell
            lines.append(
                f"{ts} | {tx.type.upper():4} | {tx.symbol} x {tx.quantity} @ {format_currency(tx.price or 0.0)} | cash Δ {format_currency(tx.cash_delta)} | id: {tx.tx_id}"
            )
    return "\n".join(lines)


def get_overall_display() -> tuple[str, str, str, str]:
    """Return (status, statement, holdings, transactions)"""
    if acct is None:
        return ("No account created. Create an account to begin.", "(no statement)", "(no holdings)", "(no transactions)")
    try:
        return ("OK", statement_text(acct), holdings_text(acct), transactions_text(acct))
    except Exception as e:
        return (f"Error generating display: {e}", "(error)", "(error)", "(error)")


# Action handlers for Gradio UI

def create_account(owner: str, initial_deposit: float) -> tuple[str, str, str, str]:
    global acct
    try:
        owner_val = owner.strip() if owner and owner.strip() else None
        # create a simple unique account id
        account_id = f"demo-{uuid.uuid4().hex[:8]}"
        acct = Account(account_id=account_id, owner=owner_val, initial_deposit=float(initial_deposit or 0.0))
        status = f"Account created: {acct.account_id} (owner: {acct.owner})"
        return (status, statement_text(acct), holdings_text(acct), transactions_text(acct))
    except AccountError as e:
        return (f"Account error: {e}", "(no statement)", "(no holdings)", "(no transactions)")
    except Exception as e:
        traceback.print_exc()
        return (f"Unexpected error: {e}", "(no statement)", "(no holdings)", "(no transactions)")


def do_deposit(amount: float, note: str) -> tuple[str, str, str, str]:
    if acct is None:
        return ("No account exists. Create one first.", "(no statement)", "(no holdings)", "(no transactions)")
    try:
        tx = acct.deposit(float(amount), note=note if note else None)
        return (f"Deposit successful: {format_currency(tx.cash_delta)}", statement_text(acct), holdings_text(acct), transactions_text(acct))
    except AccountError as e:
        return (f"Deposit failed: {e}", statement_text(acct), holdings_text(acct), transactions_text(acct))
    except Exception as e:
        traceback.print_exc()
        return (f"Unexpected error during deposit: {e}", statement_text(acct), holdings_text(acct), transactions_text(acct))


def do_withdraw(amount: float, note: str) -> tuple[str, str, str, str]:
    if acct is None:
        return ("No account exists. Create one first.", "(no statement)", "(no holdings)", "(no transactions)")
    try:
        tx = acct.withdraw(float(amount), note=note if note else None)
        return (f"Withdraw successful: {format_currency(-tx.cash_delta)}", statement_text(acct), holdings_text(acct), transactions_text(acct))
    except InsufficientFundsError as e:
        return (f"Withdraw failed: {e}", statement_text(acct), holdings_text(acct), transactions_text(acct))
    except AccountError as e:
        return (f"Withdraw error: {e}", statement_text(acct), holdings_text(acct), transactions_text(acct))
    except Exception as e:
        traceback.print_exc()
        return (f"Unexpected error during withdraw: {e}", statement_text(acct), holdings_text(acct), transactions_text(acct))


def do_buy(symbol: str, quantity: int, note: str) -> tuple[str, str, str, str]:
    if acct is None:
        return ("No account exists. Create one first.", "(no statement)", "(no holdings)", "(no transactions)")
    try:
        q = int(quantity)
        tx = acct.buy(symbol, q, price=None, note=note if note else None)
        return (f"Buy executed: {symbol} x {q} @ {format_currency(tx.price or 0.0)}  (cash Δ {format_currency(tx.cash_delta)})", statement_text(acct), holdings_text(acct), transactions_text(acct))
    except InsufficientFundsError as e:
        return (f"Buy failed - insufficient funds: {e}", statement_text(acct), holdings_text(acct), transactions_text(acct))
    except UnknownSymbolError as e:
        return (f"Buy failed - unknown symbol: {e}", statement_text(acct), holdings_text(acct), transactions_text(acct))
    except AccountError as e:
        return (f"Buy error: {e}", statement_text(acct), holdings_text(acct), transactions_text(acct))
    except Exception as e:
        traceback.print_exc()
        return (f"Unexpected error during buy: {e}", statement_text(acct), holdings_text(acct), transactions_text(acct))


def do_sell(symbol: str, quantity: int, note: str) -> tuple[str, str, str, str]:
    if acct is None:
        return ("No account exists. Create one first.", "(no statement)", "(no holdings)", "(no transactions)")
    try:
        q = int(quantity)
        tx = acct.sell(symbol, q, price=None, note=note if note else None)
        return (f"Sell executed: {symbol} x {q} @ {format_currency(tx.price or 0.0)}  (cash Δ {format_currency(tx.cash_delta)})", statement_text(acct), holdings_text(acct), transactions_text(acct))
    except InsufficientSharesError as e:
        return (f"Sell failed - insufficient shares: {e}", statement_text(acct), holdings_text(acct), transactions_text(acct))
    except UnknownSymbolError as e:
        return (f"Sell failed - unknown symbol: {e}", statement_text(acct), holdings_text(acct), transactions_text(acct))
    except AccountError as e:
        return (f"Sell error: {e}", statement_text(acct), holdings_text(acct), transactions_text(acct))
    except Exception as e:
        traceback.print_exc()
        return (f"Unexpected error during sell: {e}", statement_text(acct), holdings_text(acct), transactions_text(acct))


def show_price(symbol: str) -> str:
    try:
        price = get_share_price(symbol)
        return f"{symbol} price: {format_currency(price)}"
    except UnknownSymbolError:
        return f"Unknown symbol: {symbol}"
    except Exception as e:
        return f"Error retrieving price: {e}"


def refresh() -> tuple[str, str, str, str]:
    return get_overall_display()


# Build Gradio UI

with gr.Blocks() as demo:
    gr.Markdown("# Trading Account Demo (single-user prototype)")
    gr.Markdown("Create an account, deposit/withdraw cash, buy/sell shares. Prices are fixed for AAPL/TSLA/GOOGL in the test price provider.")

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("## Create Account")
            owner_in = gr.Textbox(label="Owner name (optional)", placeholder="Alice")
            init_deposit_in = gr.Number(value=0.0, label="Initial deposit (USD)", precision=2)
            create_btn = gr.Button("Create Account")
        with gr.Column(scale=2):
            status_out = gr.Textbox(label="Status", value="No account created.", interactive=False)
            statement_out = gr.Textbox(label="Account Statement", value="(no statement)", lines=12, interactive=False)

    with gr.Row():
        with gr.Column():
            gr.Markdown("## Cash Operations")
            deposit_amount = gr.Number(value=100.0, label="Deposit amount", precision=2)
            deposit_note = gr.Textbox(label="Deposit note (optional)")
            deposit_btn = gr.Button("Deposit")

            withdraw_amount = gr.Number(value=50.0, label="Withdraw amount", precision=2)
            withdraw_note = gr.Textbox(label="Withdraw note (optional)")
            withdraw_btn = gr.Button("Withdraw")
        with gr.Column():
            gr.Markdown("## Trade Operations")
            symbol_dropdown = gr.Dropdown(label="Symbol", choices=SUPPORTED_SYMBOLS, value=SUPPORTED_SYMBOLS[0])
            price_display = gr.Textbox(label="Current price", value=show_price(SUPPORTED_SYMBOLS[0]), interactive=False)
            qty_in = gr.Number(value=1, label="Quantity", precision=0)
            trade_note = gr.Textbox(label="Trade note (optional)")
            buy_btn = gr.Button("Buy")
            sell_btn = gr.Button("Sell")

    with gr.Row():
        with gr.Column():
            holdings_out = gr.Textbox(label="Holdings", value="(no holdings)", lines=8, interactive=False)
        with gr.Column():
            tx_out = gr.Textbox(label="Transactions (most recent first)", value="(no transactions)", lines=12, interactive=False)

    # Wire up events
    create_btn.click(create_account, inputs=[owner_in, init_deposit_in], outputs=[status_out, statement_out, holdings_out, tx_out])
    deposit_btn.click(do_deposit, inputs=[deposit_amount, deposit_note], outputs=[status_out, statement_out, holdings_out, tx_out])
    withdraw_btn.click(do_withdraw, inputs=[withdraw_amount, withdraw_note], outputs=[status_out, statement_out, holdings_out, tx_out])
    buy_btn.click(do_buy, inputs=[symbol_dropdown, qty_in, trade_note], outputs=[status_out, statement_out, holdings_out, tx_out])
    sell_btn.click(do_sell, inputs=[symbol_dropdown, qty_in, trade_note], outputs=[status_out, statement_out, holdings_out, tx_out])

    # Update price display when symbol changes
    symbol_dropdown.change(fn=show_price, inputs=[symbol_dropdown], outputs=[price_display])

    # A manual refresh button
    refresh_btn = gr.Button("Refresh display")
    refresh_btn.click(refresh, inputs=None, outputs=[status_out, statement_out, holdings_out, tx_out])

    # Initialize display values
    demo.load(fn=refresh, inputs=None, outputs=[status_out, statement_out, holdings_out, tx_out])

if __name__ == "__main__":
    demo.launch()