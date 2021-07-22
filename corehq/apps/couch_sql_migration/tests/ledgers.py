from itertools import chain, groupby

import attr

from casexml.apps.stock.models import StockTransaction

from corehq.apps.commtrack.models import StockState
from corehq.form_processor.backends.sql.dbaccessors import LedgerAccessorSQL
from corehq.form_processor.exceptions import LedgerValueNotFound


def print_ledger_history(ledger_ref, verbose=False):
    case_id, section_id, entry_id = ledger_ref.split("/")
    cch_trans = list(summarize_trans(
        CouchTransaction.to_ledgers(
            get_couch_transactions(case_id, section_id, entry_id))))
    sql_trans = list(
        summarize_trans(get_sql_transactions(case_id, section_id, entry_id)))
    print("Ledger", ledger_ref)
    print("date                      couch         sql  form/tx type")
    print("                      +/-     =   +/-     =")
    for ccht, sqlt in merge_transactions(cch_trans, sql_trans):
        both = ccht or sqlt
        ptx = verbose or \
            (ccht and sqlt and ccht.updated_balance != sqlt.updated_balance)
        header = both.report_date.strftime("%Y-%m-%d %H:%M:%S")
        footer = f"{both.form_id}  {both.server_date}"
        print_tx(header, ccht, sqlt, footer)
        if ptx:
            print_transactions(ccht, sqlt)

    try:
        stock = StockState.objects.get(
            case_id=case_id, section_id=section_id, product_id=entry_id)
    except StockState.DoesNotExist:
        class stock:
            balance = None
    try:
        ledger = LedgerAccessorSQL.get_ledger_value(
            case_id=case_id, section_id=section_id, entry_id=entry_id)
    except LedgerValueNotFound:
        class ledger:
            balance = None
    print(f"ledger value: {num(stock.balance):>17} {num(ledger.balance):>11}")


def print_tx(header, ctx, stx, footer):
    print(
        f"{header:<19}",
        f"{delta(ctx.delta) if ctx else '':>5}",
        f"{num(ctx.updated_balance) if ctx else '':>5}",
        f"{delta(stx.delta) if stx else '':>5}",
        f"{num(stx.updated_balance) if stx else '':>5} ",
        footer,
    )


def print_transactions(ccht, sqlt):
    def meaningful(tx):
        return (tx.readable_type in "stockonhand balance stockout" or (
            tx.delta and tx.readable_type in "consumption receipts transfer"
        ))
    ctxx = [tx for tx in ccht.trans if meaningful(tx)] if ccht else []
    stxx = [tx for tx in sqlt.trans if meaningful(tx)] if sqlt else []
    while True:
        if not (ctxx and stxx):
            for tx in ctxx:
                print_tx("", tx, None, tx.readable_type)
            for tx in stxx:
                print_tx("", None, tx, tx.readable_type)
            break
        if (
            ctxx[0].readable_type in "consumption receipts"
            and stxx[0].readable_type == "transfer"
        ) or (
            ctxx[0].readable_type in "stockonhand stockout"
            and stxx[0].readable_type == "balance"
        ):
            ctx = ctxx.pop(0)
            stx = stxx.pop(0)
            print_tx("", ctx, stx, f"{ctx.readable_type}/{stx.readable_type}")
        else:
            ctx = ctxx.pop(0)
            print_tx("", ctx, None, ctx.readable_type)
    print("")


def print_trans(tx):
    if isinstance(tx, CouchTransaction):
        off1 = " " * 19
        off2 = " " * 12
    else:
        off1 = " " * 31
        off2 = " " * 0
    tp = tx.readable_type
    if not (
        (tx.delta and tp in "consumption receipts transfer")
        or (tx.updated_balance and tp in "stockonhand balance")
        or tp == "stockout"
    ):
        return
    print(off1, f"{delta(tx.delta):>5} {num(tx.updated_balance):>5}" + off2, tp)


def num(value):
    if value is None:
        return ""
    if isinstance(value, int):
        return value
    if value == 0:
        return 0
    return f"{value}".rstrip("0").rstrip(".")


def delta(value):
    if value is None:
        return value
    if value == 0:
        return 0
    return f"{value:+f}".rstrip("0").rstrip(".")


def summarize_trans(transactions):
    for key, group in groupby(transactions, key=lambda t: t.form_id):
        yield FormTransactions(list(group))


def merge_transactions(cch_trans, sql_trans):
    cch_by_form = {ft.form_id: ft for ft in cch_trans}
    sql_by_form = {ft.form_id: ft for ft in sql_trans}
    seen = set()
    all_trans = chain(cch_trans, sql_trans)
    for trans in sorted(all_trans, key=lambda t: (t.report_date, t.form_id)):
        if trans.form_id not in seen:
            yield cch_by_form.get(trans.form_id), sql_by_form.get(trans.form_id)
            seen.add(trans.form_id)


@attr.s
class FormTransactions:
    trans = attr.ib()

    def __getattr__(self, name):
        values = {getattr(t, name) for t in self.trans}
        if len(values) == 1:
            return values.pop()
        raise ValueError(f"multiple values for {name}: {values}")

    @property
    def delta(self):
        return sum(t.delta for t in self.trans)

    @property
    def updated_balance(self):
        return self.trans[-1].updated_balance


@attr.s
class CouchTransaction:
    trans = attr.ib()

    @classmethod
    def to_ledgers(cls, transactions):
        return (cls(t) for t in transactions)

    def __getattr__(self, name):
        return getattr(self.trans, name)

    @property
    def report_date(self):
        return self.trans.report.date

    @property
    def server_date(self):
        return self.trans.report.server_date

    @property
    def delta(self):
        return self.trans.quantity

    @property
    def updated_balance(self):
        return self.trans.stock_on_hand

    @property
    def readable_type(self):
        return self.trans.type

    @property
    def form_id(self):
        return self.trans.report.form_id


def get_couch_transactions(case_id, section_id, product_id):
    return list(reversed(
        StockTransaction.get_ordered_transactions_for_stock(
            case_id=case_id, section_id=section_id, product_id=product_id)
        .select_related("report")
    ))


def get_sql_transactions(case_id, section_id, entry_id):
    transactions = LedgerAccessorSQL.get_ledger_transactions_for_case(
        case_id=case_id, section_id=section_id, entry_id=entry_id)
    return sorted(transactions, key=lambda t: (t.report_date, t.id))
