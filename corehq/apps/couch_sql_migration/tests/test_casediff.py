from contextlib import ExitStack
from copy import deepcopy

from django.test import SimpleTestCase

import attr
from mock import patch
from testil import Config

from corehq.form_processor.parsers.ledgers.helpers import UniqueLedgerReference

from .. import casediff as mod
from ..statedb import Change, StateDB


class TestDiffCases(SimpleTestCase):

    def setUp(self):
        super(TestDiffCases, self).setUp()
        self.patches = [
            patch(
                "corehq.blobs.metadata.MetaDB.get_for_parent",
                lambda *a: [1],
            ),
            patch(
                "corehq.form_processor.backends.sql.dbaccessors.CaseAccessorSQL.get_cases",
                self.get_sql_cases,
            ),
            patch(
                "corehq.form_processor.backends.sql.dbaccessors.FormAccessorSQL.form_exists",
                lambda *a: False,
            ),
            patch(
                "corehq.form_processor.backends.sql.dbaccessors"
                ".LedgerAccessorSQL.get_ledger_values_for_cases",
                self.get_sql_ledgers,
            ),
            patch(
                "corehq.apps.commtrack.models.StockState.objects.filter",
                self.get_stock_states,
            ),
            patch("corehq.apps.commtrack.models.StockState.include_archived.filter"),
            patch(
                "corehq.form_processor.backends.couch.dbaccessors"
                ".FormAccessorCouch.form_exists",
                fake_couch_form_exists,
            ),
            patch.object(mod, "hard_rebuild", lambda couch_case: couch_case),
            patch.object(mod, 'rebuild_and_diff_cases', self.rebuild_and_diff_cases),
            patch.object(
                mod.StockTransactionLoader,
                "get_transactions",
                self.get_stock_transactions,
            ),
            patch.object(
                mod.StockTransactionLoader,
                "iter_stock_transactions",
                self.iter_stock_transactions,
            ),
            patch.object(
                mod.StockTransactionLoader,
                "get_location",
                lambda *a: None,
            ),
        ]

        for patcher in self.patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.statedb = StateDB.init("test", ":memory:")
        self.addCleanup(self.statedb.close)
        self.sql_cases = {}
        self.sql_ledgers = {}
        self.couch_cases = {}
        self.couch_ledgers = {}
        self.stock_transactions = {}
        self.form_transactions = {}
        stack = ExitStack()
        stack.enter_context(mod.global_diff_state("test", {}))
        self.addCleanup(stack.close)

    def test_clean(self):
        self.add_case("a")
        mod.diff_cases_and_save_state(self.couch_cases, self.statedb)
        self.assert_diffs()

    def test_diff(self):
        couch_json = self.add_case("a", prop="1")
        couch_json["prop"] = "2"
        mod.diff_cases_and_save_state(self.couch_cases, self.statedb)
        self.assert_diffs([Diff("a", path=["prop"], old="2", new="1")])

    def test_wrong_domain(self):
        couch_json = self.add_case("a", prop="1", domain="wrong")
        couch_json["prop"] = 2
        mod.diff_cases_and_save_state(self.couch_cases, self.statedb)
        self.assert_diffs([Diff("a", path=["domain"], old="wrong", new="test")])

    def test_replace_diff(self):
        self.add_case("a", prop="1")
        different_cases = deepcopy(self.couch_cases)
        different_cases["a"]["prop"] = "2"
        mod.diff_cases_and_save_state(different_cases, self.statedb)
        self.assert_diffs([Diff("a", path=["prop"], old="2", new="1")])
        mod.diff_cases_and_save_state(self.couch_cases, self.statedb)
        self.assert_diffs()

    def test_case_with_missing_form(self):
        self.add_case("a", actions=[{"xform_id": "a"}], xform_ids=["a"])
        different_cases = deepcopy(self.couch_cases)
        acase = different_cases["a"]
        acase["actions"].append({"xform_id": "b"})
        acase["xform_ids"].append("b")
        mod.diff_cases_and_save_state(different_cases, self.statedb)
        self.assert_diffs([
            Diff(
                doc_id='a',
                kind='CommCareCase',
                type='set_mismatch',
                path=['xform_ids', '[*]'],
                old='b',
                new='',
            ),
            Diff(
                doc_id="a",
                path=["?"],
                old={"forms": {"b": mod.MISSING_BLOB_PRESENT}},
                new={"forms": {"b": "missing"}},
            ),
        ])

    def test_replace_ledger_diff(self):
        self.add_case("a")
        stock = self.add_ledger("a", x=1)
        stock.values["x"] = 2
        mod.diff_cases_and_save_state(self.couch_cases, self.statedb)
        self.assert_diffs([Diff("a/stock/a", "stock state", path=["x"], old=2, new=1)])
        stock.values["x"] = 1
        mod.diff_cases_and_save_state(self.couch_cases, self.statedb)
        self.assert_diffs()

    def test_ledger_missing_stock_state(self):
        self.add_case("a")
        stock = self.add_ledger("a", balance=1)
        del self.couch_ledgers["a"]
        self.stock_transactions[stock.ledger_reference] = []
        mod.diff_cases_and_save_state(self.couch_cases, self.statedb)
        self.assert_diffs([
            Diff(
                "a/stock/a", "stock state", "missing", ["*"],
                old={'form_state': mod.MISSING_BLOB_PRESENT},
                new={'form_state': 'missing', 'ledger': self.sql_ledgers["a"].to_json()},
            ),
        ])

    def test_ledger_duplicate_stock_transaction(self):
        self.add_case("a")
        stock = self.add_ledger("a", balance=1)
        stock.values["balance"] = 2
        self.stock_transactions[stock.ledger_reference] *= 3  # 2 dups
        mod.diff_cases_and_save_state(self.couch_cases, self.statedb)
        self.assert_diffs(changes=[
            Change(
                kind="stock state",
                doc_id="a/stock/a",
                reason="duplicate stock transaction",
                diff_type="diff",
                path=["balance"],
                old_value=2,
                new_value=1,
            ),
        ])

    def test_missing_sql_ledger(self):
        self.add_case("a")
        stock = self.add_ledger("a", balance=1)
        stock.values["balance"] = 2
        del self.sql_ledgers["a"]
        mod.diff_cases_and_save_state(self.couch_cases, self.statedb)
        self.assert_diffs([
            Diff(
                "a/stock/a", "stock state", "missing", ["*"],
                old={'form_state': mod.MISSING_BLOB_PRESENT, 'ledger': stock.to_json()},
                new={'form_state': 'missing'},
            ),
        ])

    def test_null_last_modified_form_id(self):
        self.add_case("a")
        stock = self.add_ledger("a", balance=1)
        stock.values["balance"] = 2
        stock.last_modified_form_id = None
        del self.sql_ledgers["a"]
        mod.diff_cases_and_save_state(self.couch_cases, self.statedb)
        self.assert_diffs([
            Diff(
                "a/stock/a", "stock state", "missing", ["*"],
                old={'form_state': 'unknown', 'ledger': stock.to_json()},
                new={'form_state': 'unknown'},
            ),
        ])

    def assert_diffs(self, expected=None, changes=None):
        actual = [
            Diff(diff.doc_id, diff.kind, *diff.json_diff)
            for diff in self.statedb.get_diffs()
        ]
        self.assertEqual(actual, expected or [])
        changes = changes or []
        saved_changes = list(self.statedb.iter_changes())
        self.assertEqual(saved_changes, changes,
            "all changes:\n" + "\n".join(repr(c) for c in changes))

    def add_case(self, case_id, **props):
        assert case_id not in self.sql_cases, self.sql_cases[case_id]
        assert case_id not in self.couch_cases, self.couch_cases[case_id]
        props.setdefault("domain", self.statedb.domain)
        props.setdefault("doc_type", "CommCareCase")
        props.setdefault("_id", case_id)
        props.setdefault("actions", [])
        self.sql_cases[case_id] = Config(
            case_id=case_id,
            props=props,
            to_json=lambda: dict(props, case_id=case_id),
            is_deleted=False,
            xform_ids=[],
        )
        self.couch_cases[case_id] = couch_case = dict(props, case_id=case_id)
        return couch_case

    def add_ledger(self, case_id, **values):
        ref = UniqueLedgerReference(case_id, "stock", case_id)
        self.sql_ledgers[case_id] = Config(
            ledger_reference=ref,
            values=values,
            last_modified_form_id="form",
            to_json=lambda: dict(values, ledger_reference=ref.as_id()),
        )
        couch_values = dict(values)
        stock = Config(
            ledger_reference=ref,
            values=couch_values,
            last_modified_form_id="form",
            to_json=lambda: dict(couch_values, ledger_reference=ref.as_id()),
        )
        self.couch_ledgers[case_id] = stock
        tx = Config(
            report=Config(form_id="form", type="transfer"),
            ledger_reference=ref,
        )
        tx_helper = Config(ledger_reference=ref)
        self.stock_transactions[ref] = [tx]
        self.form_transactions["form"] = [("transfer", tx_helper)]
        return stock

    def get_sql_cases(self, case_ids):
        return [self.sql_cases[c] for c in case_ids]

    def get_sql_ledgers(self, case_ids):
        ledgers = self.sql_ledgers
        return [ledgers[c] for c in case_ids if c in ledgers]

    def get_stock_states(self, case_id__in):
        ledgers = self.couch_ledgers
        return [ledgers[c] for c in case_id__in if c in ledgers]

    def get_stock_transactions(self, ref):
        return self.stock_transactions[ref]

    def iter_stock_transactions(self, form_id):
        yield from self.form_transactions[form_id]

    def rebuild_and_diff_cases(self, sql_case, couch_case, orig, diff, dd_count):
        sql_json = sql_case.to_json()
        return sql_json, diff(couch_case, sql_json)


@attr.s
class Diff:
    doc_id = attr.ib()
    kind = attr.ib(default="CommCareCase")
    type = attr.ib(default="diff")
    path = attr.ib(factory=list)
    old = attr.ib(default=None)
    new = attr.ib(default=None)


def fake_couch_form_exists(form_id):
    if not isinstance(form_id, str):
        raise TypeError
    return False
