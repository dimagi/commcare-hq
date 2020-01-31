import logging
from collections import defaultdict
from contextlib import contextmanager
from functools import partial

import attr

from casexml.apps.case.xform import get_case_ids_from_form
from casexml.apps.stock.models import StockTransaction
from dimagi.utils.couch.database import retry_on_couch_error

from corehq.apps.commtrack.models import StockState
from corehq.apps.locations.models import SQLLocation
from corehq.apps.tzmigration.timezonemigration import FormJsonDiff as Diff
from corehq.apps.tzmigration.timezonemigration import json_diff
from corehq.blobs import get_blob_db
from corehq.form_processor.backends.couch.dbaccessors import (
    CaseAccessorCouch,
    FormAccessorCouch,
)
from corehq.form_processor.backends.couch.processor import FormProcessorCouch
from corehq.form_processor.backends.sql.dbaccessors import (
    CaseAccessorSQL,
    FormAccessorSQL,
    LedgerAccessorSQL,
)
from corehq.form_processor.exceptions import MissingFormXml
from corehq.form_processor.parsers.ledgers.form import (
    get_all_stock_report_helpers_from_form,
)
from corehq.util.datadog.gauges import datadog_counter

from .diff import filter_case_diffs, filter_ledger_diffs
from .rebuildcase import rebuild_and_diff_cases
from .statedb import Change

log = logging.getLogger(__name__)


def diff_cases_and_save_state(couch_cases, statedb):
    """Diff a batch of cases

    There is a small chance that two concurrent calls to this function,
    each having copies of the same case could write conflicting diffs to
    the state db (worst case: duplicate diffs in case db). It is even
    more unlikely that the relevant SQL case would also be changed at
    the same time, resulting in the outcome of the concurrent diffs to
    be different (worst case: replace real diff with none). Luckly a
    concurrent change to the SQL case will cause a subsequent diff to be
    queued to happen at a later time, which will replace any conflicting
    case diffs in the state db.

    :param couch_cases: dict `{<case_id>: <case_json>, ...}`
    """
    log.debug('Calculating case diffs for {} cases'.format(len(couch_cases)))
    data = diff_cases(couch_cases)
    make_result_saver(statedb)(data)


def make_result_saver(statedb, count_cases=lambda n: None):
    """Make function to save case diff results to statedb"""
    def save_result(data):
        count_cases(len(data.doc_ids))
        statedb.add_diffed_cases(data.doc_ids)
        statedb.replace_case_diffs(data.diffs)
        statedb.replace_case_changes(data.changes)
        for doc_type, doc_ids in data.missing_docs:
            statedb.add_missing_docs(doc_type, doc_ids)
    return save_result


def diff_cases(couch_cases, log_cases=False):
    """Diff cases and return diff data

    :param couch_cases: dict `{<case_id>: <case_json>, ...}`
    :returns: `DiffData`
    """
    assert isinstance(couch_cases, dict), repr(couch_cases)[:100]
    assert "_diff_state" in globals()
    data = DiffData()
    dd_count = partial(datadog_counter, tags=["domain:" + _diff_state.domain])
    case_ids = list(couch_cases)
    sql_case_ids = set()
    for sql_case in CaseAccessorSQL.get_cases(case_ids):
        case_id = sql_case.case_id
        sql_case_ids.add(case_id)
        couch_case, diffs, changes = diff_case(sql_case, couch_cases[case_id], dd_count)
        if diffs:
            dd_count("commcare.couchsqlmigration.case.has_diff")
        data.doc_ids.append(case_id)
        data.diffs.append((couch_case['doc_type'], case_id, diffs))
        data.changes.append((couch_case['doc_type'], case_id, changes))
        if log_cases:
            log.info("case %s -> %s diffs", case_id, len(diffs))

    diffs, changes = diff_ledgers(case_ids, dd_count)
    data.diffs.extend(diffs)
    data.changes.extend(changes)
    add_missing_docs(data, couch_cases, sql_case_ids, dd_count)
    return data


def diff_case(sql_case, couch_case, dd_count):
    def diff(couch_json, sql_json):
        diffs = json_diff(couch_json, sql_json, track_list_indices=False)
        return filter_case_diffs(couch_json, sql_json, diffs, _diff_state)
    case_id = couch_case['_id']
    sql_json = sql_case.to_json()
    dd_count("commcare.couchsqlmigration.case.diffed")
    diffs = check_domains(case_id, couch_case, sql_json)
    changes = []
    if diffs:
        return couch_case, diffs, changes
    original_couch_case = couch_case
    diffs = diff(couch_case, sql_json)
    if diffs:
        dd_count("commcare.couchsqlmigration.case.rebuild.couch")
        try:
            couch_case = hard_rebuild(couch_case)
        except Exception as err:
            dd_count("commcare.couchsqlmigration.case.rebuild.error")
            log.warning(f"Case {case_id} rebuild -> {type(err).__name__}: {err}")
        else:
            diffs = diff(couch_case, sql_json)
            if diffs:
                sql_json, diffs = rebuild_and_diff_cases(sql_case, couch_case, diff, dd_count)
            if not diffs:
                changes = diffs_to_changes(diff(original_couch_case, sql_json), "rebuild case")
            elif not diff(original_couch_case, sql_json):
                log.warning("original couch case matches rebuilt SQL case "
                    "(unexpected, rebuild not saved)")
            else:
                assert diffs
                diffs.extend(diff_case_forms(couch_case, sql_json))
    return couch_case, diffs, changes


def check_domains(case_id, couch_json, sql_json):
    if couch_json["domain"] == _diff_state.domain:
        if sql_json["domain"] == _diff_state.domain:
            return []
        log.warning("sql case %s has wrong domain: %s", case_id, sql_json["domain"])
        diffs = json_diff({"domain": _diff_state.domain}, {"domain": sql_json["domain"]})
    else:
        log.warning("couch case %s has wrong domain: %s", case_id, couch_json["domain"])
        diffs = json_diff({"domain": couch_json["domain"]}, {"domain": _diff_state.domain})
    assert diffs, "expected domain diff"
    return diffs


@retry_on_couch_error
def hard_rebuild(couch_case):
    return FormProcessorCouch.hard_rebuild_case(
        couch_case["domain"], couch_case['_id'], None, save=False, lock=False
    ).to_json()


def diff_ledgers(case_ids, dd_count):
    def diff(couch_state, ledger_value):
        couch_json = couch_state.to_json() if couch_state is not None else {}
        diffs = json_diff(couch_json, ledger_value.to_json(), track_list_indices=False)
        return filter_ledger_diffs(diffs)
    stock_tx = StockTransactionLoader()
    couch_state_map = {
        state.ledger_reference: state
        for state in StockState.objects.filter(case_id__in=case_ids)
    }
    sql_refs = set()
    all_diffs = []
    all_changes = []
    for ledger_value in LedgerAccessorSQL.get_ledger_values_for_cases(case_ids):
        ref = ledger_value.ledger_reference
        sql_refs.add(ref)
        dd_count("commcare.couchsqlmigration.ledger.diffed")
        couch_state = couch_state_map.get(ref, None)
        if couch_state is None:
            couch_state = stock_tx.get_stock_state(ref)
            dd_count("commcare.couchsqlmigration.ledger.rebuild")
        if couch_state is None:
            diffs = [stock_tx.diff_missing_ledger(ledger_value)]
        else:
            diffs = diff(couch_state, ledger_value)
            if diffs and stock_tx.has_duplicate_transactions(ref):
                changes = diffs_to_changes(diffs, "duplicate stock transaction")
                all_changes.append(("stock state", ref.as_id(), changes))
                diffs = []
        if diffs:
            dd_count("commcare.couchsqlmigration.ledger.has_diff")
        all_diffs.append(("stock state", ref.as_id(), diffs))
    for ref, couch_state in couch_state_map.items():
        if ref not in sql_refs:
            diffs = [stock_tx.diff_missing_ledger(couch_state, sql_miss=True)]
            dd_count("commcare.couchsqlmigration.ledger.diffed")
            dd_count("commcare.couchsqlmigration.ledger.has_diff")
            all_diffs.append(("stock state", ref.as_id(), diffs))
    return all_diffs, all_changes


class StockTransactionLoader:

    def __init__(self):
        self.stock_transactions = {}
        self.case_locations = {}
        self.ledger_refs = {}

    def get_stock_state(self, ref):
        """Build stock state JSON from latest transaction

        Returns empty dict if stock transactions do not exist.
        """
        # similar to StockTransaction.latest(), but more efficient
        transactions = self.get_transactions(ref)
        if not transactions:
            return None
        transaction = transactions[0]
        return self.new_stock_state(ref, transaction)

    def has_duplicate_transactions(self, ref):
        """Return true if any of ref's transactions are duplicates

        A transaction is a duplicate if there are less ledger references
        of its report type in the form than there are transactions of
        the same report type referencing that form.
        """
        txx = defaultdict(int)
        for tx in self.get_transactions(ref):
            txx[(tx.report.form_id, tx.report.type)] += 1
        return any(
            self.count_ledger_refs(form_id, report_type, ref) < num_tx
            for (form_id, report_type), num_tx in txx.items() if num_tx > 1
        )

    def diff_missing_ledger(self, ledger, *, sql_miss=False):
        """Get the state of the form reference by ledger

        :param ledger: Object having `last_modified_form_id` attribute
        (`LedgerValue` or `StockState`).
        """
        form_id = ledger.last_modified_form_id
        old, new = diff_form_state(form_id, in_couch=form_id in self.ledger_refs)
        if sql_miss:
            old["ledger"] = ledger.to_json()
        else:
            new["ledger"] = ledger.to_json()
        return Diff("missing", path=["*"], old_value=old, new_value=new)

    def get_transactions(self, ref):
        cache = self.stock_transactions
        if ref.case_id not in cache:
            case_txx = list(StockTransaction.objects
                .filter(case_id=ref.case_id)
                .order_by('-report__date', '-pk')
                .select_related("report"))
            case_cache = cache[ref.case_id] = defaultdict(list)
            for tx in case_txx:
                case_cache[tx.ledger_reference].append(tx)
        return cache[ref.case_id][ref]

    def new_stock_state(self, ref, transaction):
        return StockState(
            case_id=ref.case_id,
            section_id=ref.section_id,
            product_id=ref.entry_id,
            sql_location=self.get_location(ref.case_id),
            last_modified_date=transaction.report.server_date,
            last_modified_form_id=transaction.report.form_id,
            stock_on_hand=transaction.stock_on_hand,
        )

    def get_location(self, case_id):
        try:
            loc = self.case_locations[case_id]
        except KeyError:
            loc = SQLLocation.objects.get_or_None(supply_point_id=case_id)
            self.case_locations[case_id] = loc
        return loc

    def count_ledger_refs(self, form_id, report_type, ref):
        if form_id not in self.ledger_refs:
            ref_counts = defaultdict(lambda: defaultdict(int))
            for tx_report_type, tx in self.iter_stock_transactions(form_id):
                ref_counts[tx_report_type][tx.ledger_reference] += 1
            self.ledger_refs[form_id] = ref_counts
        num = self.ledger_refs[form_id][report_type][ref]
        assert num > 0, (form_id, report_type, ref)
        return num

    def iter_stock_transactions(self, form_id):
        xform = FormAccessorCouch.get_form(form_id)
        assert xform.domain == _diff_state.domain, xform
        for report in get_all_stock_report_helpers_from_form(xform):
            for tx in report.transactions:
                yield report.report_type, tx


def diff_case_forms(couch_json, sql_json):
    couch_ids = {a["xform_id"] for a in couch_json["actions"] if a["xform_id"]}
    sql_ids = {t["xform_id"] for t in sql_json["actions"] if t["xform_id"]}
    only_in_couch = couch_ids - sql_ids
    if not only_in_couch:
        return []
    old_forms = {}
    new_forms = {}
    for form_id in only_in_couch:
        old, new = diff_form_state(form_id)
        old_forms[form_id] = old["form_state"]
        new_forms[form_id] = new["form_state"]
    if any(v.startswith("missing") for v in old_forms.values()):
        return [Diff(
            "diff",
            path=["?"],
            old_value={"forms": old_forms},
            new_value={"forms": new_forms},
        )]
    return []


def diff_form_state(form_id, *, in_couch=False):
    in_couch = in_couch or FormAccessorCouch.form_exists(form_id)
    in_sql = FormAccessorSQL.form_exists(form_id)
    couch_miss = "missing"
    if not in_couch and get_blob_db().metadb.get_for_parent(form_id):
        couch_miss = "missing, blob present"
    old = {"form_state": "present" if in_couch else couch_miss}
    new = {"form_state": "present" if in_sql else "missing"}
    return old, new


def add_missing_docs(data, couch_cases, sql_case_ids, dd_count):
    if len(couch_cases) != len(sql_case_ids):
        only_in_sql = sql_case_ids - couch_cases.keys()
        assert not only_in_sql, only_in_sql
        only_in_couch = couch_cases.keys() - sql_case_ids
        data.doc_ids.extend(only_in_couch)
        missing_cases = [couch_cases[x] for x in only_in_couch]
        dd_count("commcare.couchsqlmigration.case.missing_from_sql", value=len(missing_cases))
        for doc_type, doc_ids in filter_missing_cases(missing_cases):
            data.missing_docs.append((doc_type, doc_ids))


def filter_missing_cases(missing_cases):
    result = defaultdict(list)
    for couch_case in missing_cases:
        if is_orphaned_case(couch_case):
            log.info("Ignoring orphaned case: %s", couch_case["_id"])
        else:
            result[couch_case["doc_type"]].append(couch_case["_id"])
    return result.items()


@contextmanager
def global_diff_state(domain, no_action_case_forms, cutoff_date=None):
    from .couchsqlmigration import migration_patches
    global _diff_state
    _diff_state = WorkerState(domain, no_action_case_forms, cutoff_date)
    try:
        with migration_patches():
            yield
    finally:
        del _diff_state


@attr.s
class DiffData:
    doc_ids = attr.ib(factory=list)
    diffs = attr.ib(factory=list)
    missing_docs = attr.ib(factory=list)

    # Changes are diffs that cannot be resolved due to a feature or bug
    # in the Couch form processor that is not present in the SQL form
    # processor. Examples:
    # - Couch rebuild changes the state of the case
    # - duplicate stock transactions in Couch resulting in incorrect balances
    changes = attr.ib(factory=list)


def diffs_to_changes(diffs, reason):
    return [
        Change(kind=None, doc_id=None, reason=reason, **diff._asdict())
        for diff in diffs
    ]


@attr.s
class WorkerState:
    domain = attr.ib()
    forms = attr.ib(repr=lambda v: repr(v) if callable(v) else f"[{len(v)} ids]")
    cutoff_date = attr.ib()

    def __attrs_post_init__(self):
        if callable(self.forms):
            self.get_no_action_case_forms = self.forms
        if self.cutoff_date is None:
            self.should_diff = lambda case: True

    def get_no_action_case_forms(self):
        return self.forms

    def should_diff(self, case):
        return (
            case.server_modified_on is None
            or case.server_modified_on < self.cutoff_date
        )


def is_orphaned_case(couch_case):
    def references_case(form_id):
        form = FormAccessorCouch.get_form(form_id)
        try:
            return case_id in get_case_ids_from_form(form)
        except MissingFormXml:
            return True  # assume case is referenced if form XML is missing

    case_id = couch_case["_id"]
    return not any(references_case(x) for x in couch_case["xform_ids"])


@retry_on_couch_error
def get_couch_cases(case_ids):
    return CaseAccessorCouch.get_cases(case_ids)
