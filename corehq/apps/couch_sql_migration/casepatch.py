import json
import logging
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from functools import partial, wraps
from uuid import uuid4
from xml.etree import cElementTree as ElementTree
from xml.sax.saxutils import escape

from django.template.loader import render_to_string

import attr
from memoized import memoized

from casexml.apps.case import const
from casexml.apps.case.sharedmodels import CommCareCaseIndex
from casexml.apps.case.xml.parser import KNOWN_PROPERTIES
from casexml.apps.phone.xml import get_case_xml
from casexml.apps.stock.mock import Balance, Entry
from casexml.apps.stock.models import StockTransaction
from dimagi.utils.parsing import json_format_datetime

from corehq.apps.commtrack.models import StockState
from corehq.apps.locations.models import SQLLocation
from corehq.apps.tzmigration.timezonemigration import FormJsonDiff, MISSING
from corehq.blobs import get_blob_db
from corehq.form_processor.backends.sql.dbaccessors import LedgerAccessorSQL
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.models import (
    Attachment,
    XFormInstanceSQL,
    XFormOperationSQL,
)
from corehq.form_processor.parsers.ledgers.helpers import UniqueLedgerReference
from corehq.util.dates import iso_string_to_datetime
from corehq.util.metrics import metrics_counter

from .casediff import get_domain
from .casedifftool import format_diffs
from .couchsqlmigration import get_case_and_ledger_updates, save_migrated_models
from .retrydb import get_couch_case

log = logging.getLogger(__name__)


def patch_diffs(doc_diffs, log_cases=False):
    """Patch case diffs

    :param doc_diffs: List of three-tuples as returned by
    `StateDB.iter_doc_diffs()`.
    :returns: A list of case ids to re-diff.
    """
    pending_diffs = []
    dd_count = partial(metrics_counter, tags={"domain": get_domain()})
    for kind, case_id, diffs in doc_diffs:
        if kind != "CommCareCase":
            log.warning("cannot patch %s: %s", kind, case_id)
            continue
        dd_count("commcare.couchsqlmigration.case.patch")
        try:
            patch_case(case_id, diffs)
        except CannotPatch as err:
            error_diffs = [(kind, case_id, err.diffs)]
            log.warning("cannot patch %s", format_diffs(error_diffs))
            continue
        except Exception:
            error_diffs = [(kind, case_id, [d.json_diff for d in diffs])]
            log.exception("cannot patch %s", format_diffs(error_diffs))
            continue
        pending_diffs.append(case_id)
    return pending_diffs


def patch_case(case_id, diffs):
    def is_ledger(diff):
        return diff.kind == "stock state"
    try:
        couch_case = get_couch_case(case_id)
    except CaseNotFound:
        raise CannotPatch(diffs)
    assert couch_case.domain == get_domain(), (couch_case, get_domain())
    case_diffs = [d.json_diff for d in diffs if not is_ledger(d)]
    ledger_diffs = [LedgerDiff(d) for d in diffs if is_ledger(d)]
    case = PatchCase(couch_case, case_diffs, ledger_diffs)
    form = PatchForm(case)
    process_patch(form)


def aslist(generator_func):
    @wraps(generator_func)
    def wrapper(*args, **kw):
        return list(generator_func(*args, **kw))
    return wrapper


@attr.s(hash=False)
class PatchCase:
    case = attr.ib()
    diffs = attr.ib()
    ledger_diffs = attr.ib()

    def __attrs_post_init__(self):
        assert self.diffs or self.ledger_diffs, "PatchCase must have diffs"
        self.case_attachments = []
        self._updates = updates = []
        if is_missing_in_sql(self.diffs):
            updates.extend([const.CASE_ACTION_CREATE, const.CASE_ACTION_UPDATE])
            self._dynamic_properties = self.case.dynamic_case_properties()
        else:
            if has_illegal_props(self.diffs):
                raise CannotPatch(self.diffs)
            props = dict(iter_dynamic_properties(self.diffs))
            self._dynamic_properties = props
            if props or has_known_props(self.diffs) or self.indices:
                updates.append(const.CASE_ACTION_UPDATE)
        if self._should_close():
            updates.append(const.CASE_ACTION_CLOSE)

    def __hash__(self):
        return hash(self.case_id)

    def __getattr__(self, name):
        return getattr(self.case, name)

    def _should_close(self):
        return self.case.closed and (
            any(d.path == ["closed"] and not d.new_value for d in self.diffs)
            or is_missing_in_sql(self.diffs)
        )

    def dynamic_case_properties(self):
        return self._dynamic_properties

    @property
    @memoized
    @aslist
    def indices(self):
        diffs = [d for d in self.diffs if d.path[0] == "indices"]
        if not diffs:
            if is_missing_in_sql(self.diffs):
                yield from self.case.indices
            return
        for diff in diffs:
            if diff.path != ["indices", "[*]"]:
                raise CannotPatch([diff])
            if diff.new_value is MISSING and isinstance(diff.old_value, dict):
                yield CommCareCaseIndex.wrap(diff.old_value)
            elif diff.old_value is MISSING and isinstance(diff.new_value, dict):
                yield CommCareCaseIndex(
                    identifier=diff.new_value["identifier"],
                    referenced_type="",
                )
            else:
                raise CannotPatch([diff])

    def iter_xml_blocks(self):
        yield get_case_xml(self, self._updates, version='2.0')
        yield from self._ledger_blocks()
        yield get_diff_block(self).encode('utf-8')

    def _ledger_blocks(self):
        for diff in self.ledger_diffs:
            if is_ledger_patchable(diff):
                yield get_ledger_patch_xml(diff)


def has_illegal_props(diffs):
    return any(d.path[0] in ILLEGAL_PROPS for d in diffs)


def has_known_props(diffs):
    return any(d.path[0] in KNOWN_PROPERTIES for d in diffs)


def iter_dynamic_properties(diffs):
    for diff in diffs:
        name = diff.path[0]
        if name in STATIC_PROPS:
            continue
        if diff.old_value is MISSING:
            value = ""
        elif len(diff.path) > 1 or not isinstance(diff.old_value, str):
            raise CannotPatch([diff])
        else:
            value = diff.old_value
        yield name, value


ILLEGAL_PROPS = {"actions", "case_id", "domain", "*"}
UNPATCHABLE_PROPS = {
    "closed_by",
    "closed_on",
    "deleted_on",
    "deletion_id",
    "external_id",
    "modified_by",
    "modified_on",
    "opened_by",
    "opened_on",
    "server_modified_on",
    "xform_ids",
}
STATIC_PROPS = {
    "case_id",
    "closed",
    "closed_by",
    "closed_on",
    "deleted",
    "deleted_on",
    "deletion_id",
    "domain",
    "external_id",
    "indices",
    "location_id",
    "modified_by",
    "modified_on",
    "name",
    "opened_by",
    "opened_on",
    "owner_id",
    "server_modified_on",
    "type",
    "user_id",
    "xform_ids",

    # renamed/obsolete Couch properties
    "-deletion_date",   # deleted_on
    "-deletion_id",     # deletion_id
    "@date_modified",   # modified_on
    "@user_id",         # user_id
    "hq_user_id",       # external_id
    "#text",            # ignore that junk
}


@attr.s
class PatchForm:
    _case = attr.ib()
    form_id = attr.ib(factory=lambda: uuid4().hex, init=False)
    received_on = attr.ib(factory=datetime.utcnow, init=False)
    device_id = "couch-to-sql/patch-case-diff"
    xmlns = f"http://commcarehq.org/{device_id}"
    _proxy_attrs = {"domain", "user_id"}

    def __getattr__(self, name):
        if name in self._proxy_attrs:
            return getattr(self._case, name)
        raise AttributeError(name)

    @memoized
    def get_xml(self):
        return render_to_string('hqcase/xml/case_block.xml', {
            'xmlns': self.xmlns,
            'case_block': b''.join(self._case.iter_xml_blocks()).decode('utf-8'),
            'time': json_format_datetime(self.received_on),
            'uid': self.form_id,
            'username': "",
            'user_id': self.user_id or "",
            'device_id': self.device_id,
        })


def process_patch(patch_form):
    sql_form = XFormInstanceSQL(
        form_id=patch_form.form_id,
        domain=patch_form.domain,
        xmlns=patch_form.xmlns,
        user_id=patch_form.user_id,
        received_on=patch_form.received_on,
    )
    add_form_xml(sql_form, patch_form)
    add_patch_operation(sql_form)
    case_stock_result = get_case_and_ledger_updates(patch_form.domain, sql_form)
    save_migrated_models(sql_form, case_stock_result)
    patch_ledgers_directly(patch_form._case.ledger_diffs)


def add_form_xml(sql_form, patch_form):
    xml = patch_form.get_xml()
    att = Attachment("form.xml", xml.encode("utf-8"), content_type="text/xml")
    xml_meta = att.write(get_blob_db(), sql_form)
    sql_form.attachments_list = [xml_meta]


def add_patch_operation(sql_form):
    sql_form.track_create(XFormOperationSQL(
        form=sql_form,
        user_id=sql_form.user_id,
        date=datetime.utcnow(),
        operation="Couch to SQL case patch"
    ))


def get_diff_block(case):
    """Get XML element containing case diff data

    Some early patch forms were submitted without this element.

    :param case: `PatchCase` instance.
    :returns: A "<diff>" XML element string containing XML-escaped
    JSON-encoded case diff data, some of which may be patched.

    ```json
    {
        "case_id": case.case_id,
        "diffs": [  # optional, omitted if there are no case diffs
            {
                "path": diff.path,
                "old": diff.old_value,  # omitted if old_value is MISSING
                "new": diff.new_value,  # omitted if new_value is MISSING
                "patch": true if patched else false
                "reason": "...",  # omitted if reason for change is unknown
            },
            ...
        ],
        "ledgers": {  # optional, omitted if there are no ledger diffs
            diff.doc_id: [
                {
                    # same fields as case diffs
                    # plus extra field if path == ["balance"]:
                    "couch_transactions": [
                        # items produced by ledger_transaction_json()
                    ]
                },
                ...
            ],
            ...
        }
    }
    ```
    """
    data = {"case_id": case.case_id}
    if case.diffs:
        data["diffs"] = [
            diff_to_json(d)
            for d in sorted(case.diffs, key=lambda d: d.path)
        ]
    if case.ledger_diffs:
        ledger_diffs = defaultdict(list)
        for diff in sorted(case.ledger_diffs, key=lambda d: d.path):
            ledger_diffs[diff.doc_id].append(diff_to_json(diff))
        data["ledgers"] = dict(ledger_diffs)
    return f"<diff>{escape(json.dumps(data))}</diff>"


def diff_to_json(diff, new_value=None):
    assert diff.old_value is not MISSING or diff.new_value is not MISSING, diff
    assert not isinstance(diff.path, str), diff  # PlanningDiff not allowed
    obj = {"path": list(diff.path), "patch": is_patchable(diff)}
    if diff.old_value is not MISSING:
        obj["old"] = jsonify(diff.old_value)
    if diff.new_value is not MISSING:
        obj["new"] = jsonify(diff.new_value) if new_value is None else new_value
    if isinstance(diff, LedgerDiff) and obj["path"] == ["balance"]:
        obj["couch_transactions"] = get_couch_transactions(diff.ref)
    if getattr(diff, "reason", ""):
        obj["reason"] = diff.reason
    return obj


def is_patchable(diff):
    if isinstance(diff, LedgerDiff):
        return is_ledger_patchable(diff)
    assert not isinstance(diff.path, str), diff  # PlanningDiff not allowed
    return not (diff.path[0] in UNPATCHABLE_PROPS or (
        list(diff.path) == ["closed"] and not diff.old_value and diff.new_value
    ))


def is_ledger_patchable(diff):
    return not (
        tuple(diff.path) in UNPATCHABLE_LEDGER_PATHS
        or is_couch_ledger_missing(diff)
        or is_couch_stock_state_missing(diff)
    )


def is_couch_ledger_missing(diff):
    return (
        list(diff.path) == ["*"]
        and diff.diff_type == "missing"
        and isinstance(diff.old_value, dict)
        and isinstance(diff.new_value, dict)
        and diff.old_value.keys() == {"form_state"}
        and diff.new_value.keys() == {"form_state", "ledger"}
    )


def is_couch_stock_state_missing(diff):
    ref = diff.ref
    return list(diff.path) == ["balance"] and not StockState.include_archived.filter(
        case_id=ref.case_id,
        section_id=ref.section_id,
        product_id=ref.entry_id,
    ).exists()


UNPATCHABLE_LEDGER_PATHS = {
    ("last_modified",),
    ("last_modified_form_id",),
}


def get_ledger_patch_xml(diff):
    path = list(diff.path)
    if path == ["balance"]:
        element = ledger_balance_patch(diff)
    elif (
        path == ["*"]
        and diff.diff_type == "missing"
        and isinstance(diff.old_value, dict)
        and isinstance(diff.new_value, dict)
        and diff.old_value.keys() == {"form_state", "ledger"}
        and diff.new_value.keys() == {"form_state"}
    ):
        element = missing_ledger_patch(diff)
    elif (
        path == ["daily_consumption"]
        and diff.diff_type == "type"
        and isinstance(diff.old_value, str)
        and diff.new_value is None
    ):
        element = None
    elif (
        path == ["location_id"]
        and diff.diff_type == "type"
        and isinstance(diff.old_value, str)
        and diff.new_value is None
    ):
        element = None
    else:
        raise CannotPatch([diff])
    if element is None:
        return b""
    return ElementTree.tostring(element.as_xml(), encoding='utf-8')


def ledger_balance_patch(diff):
    assert isinstance(diff.old_value, (Decimal, int, float)), diff
    ref = diff.ref
    stock = StockState.include_archived.get(
        case_id=ref.case_id,
        section_id=ref.section_id,
        product_id=ref.entry_id,
    )
    return Balance(
        entity_id=ref.case_id,
        date=stock.last_modified_date.date(),
        section_id=ref.section_id,
        entry=Entry(id=ref.entry_id, quantity=diff.old_value),
    )


def missing_ledger_patch(diff):
    ref = diff.ref
    data = diff.old_value["ledger"]
    return Balance(
        entity_id=ref.case_id,
        date=iso_string_to_datetime(data["last_modified"]).date(),
        section_id=ref.section_id,
        entry=Entry(id=ref.entry_id, quantity=data["balance"]),
    )


def patch_ledgers_directly(diffs):
    """Update ledger values directly rather than patching via form submission

    This is necessary because some operations are not done as a result of
    form submissions in the context of a migration. Example: publishing to
    Kafka change feeds is disabled during the migration.
    """
    for diff in diffs:
        path = list(diff.path)
        if diff.diff_type == "type" and diff.new_value is None:
            if path == ["daily_consumption"]:
                patch_ledger_daily_consumption(diff)
            if path == ["location_id"]:
                patch_ledger_location_id(diff)


def patch_ledger_daily_consumption(diff):
    """Patch missing LedgerValue daily_consumption

    This is deliberately done as a patch action rather than
    automatically as part of the main migration to leave an audit trail
    showing that the difference existed in the initial happy-path
    migration phase. The migration does not publish ledger changes to
    Kafka change feeds where daily_consumption is normally calculated.
    Instead the value is copied from the Couch StockState.
    """
    ref = diff.ref
    ledger = LedgerAccessorSQL.get_ledger_value(
        ref.case_id, ref.section_id, ref.entry_id
    )
    assert ledger.daily_consumption is None, ref
    ledger.daily_consumption = diff.old_value
    ledger.save()


def patch_ledger_location_id(diff):
    """Patch missing LedgerValue location_id"""
    location = SQLLocation.objects.select_related("location_type").get(location_id=diff.old_value)
    if location.location_type.administrative:
        raise CannotPatch([diff])
    location.supply_point_id = diff.ref.case_id
    location.save()


def get_couch_transactions(ref):
    return [ledger_transaction_json(tx) for tx in reversed(
        StockTransaction.get_ordered_transactions_for_stock(
            case_id=ref.case_id,
            section_id=ref.section_id,
            product_id=ref.entry_id,
        ).select_related("report")
    )]


def ledger_transaction_json(tx):
    return {
        "form_id": tx.report.form_id,
        "type": tx.type,
        "delta": jsonify(tx.quantity),
        "balance": jsonify(tx.stock_on_hand),
    }


def jsonify(value):
    if isinstance(value, Decimal):
        return int(value) if int(value) == value else float(value)
    return value


class LedgerDiff:
    """Ledger diff

    Has the same fields as `FormJsonDiff` in addition to `doc_id`
    (`str`) and `ref` (`UniqueLedgerReference`) attributes. May be
    instantiated two ways:

    - Single argument: PlanningDiff-like with `json_diff` and `doc_id`
      attributes.
    - Two arguments: FormJsonDiff-like, UniqueLedgerReference

    Yes, keeping all the diff types straight is a nightmare! Fixing that
    would require refactoring the `tzmigration` app and migrating data
    in various SQLite databases, which is out of scope.
    """

    def __init__(self, diff, ref=None):
        if ref is None:
            ref = UniqueLedgerReference.from_id(diff.doc_id)
            diff = diff.json_diff
        else:
            assert not isinstance(diff.path, str), (ref, diff)
        self.ref = ref
        for name in FormJsonDiff._fields:
            setattr(self, name, getattr(diff, name))

    def __repr__(self):
        fields = " ".join(
            f"{name}={getattr(self, name)!r}"
            for name in FormJsonDiff._fields
        )
        return f"<LedgerDiff {self.doc_id} {fields}>"

    @property
    def doc_id(self):
        return self.ref.as_id()


class CannotPatch(Exception):

    def __init__(self, json_diffs):
        super().__init__(repr(json_diffs))
        self.diffs = json_diffs


def is_missing_in_sql(diffs):
    if not diffs:
        return False
    diff = diffs[0]
    return (
        len(diffs) == 1
        and diff.diff_type == "missing"
        and diff.path == ['*']
        and diff.old_value is not MISSING
        and diff.new_value is MISSING
    )
