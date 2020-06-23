import json
import logging
from datetime import datetime
from functools import partial, wraps
from uuid import uuid4
from xml.sax.saxutils import escape

from django.template.loader import render_to_string

import attr
from memoized import memoized

from casexml.apps.case import const
from casexml.apps.case.sharedmodels import CommCareCaseIndex
from casexml.apps.case.xml.parser import KNOWN_PROPERTIES
from casexml.apps.phone.xml import get_case_xml
from dimagi.utils.parsing import json_format_datetime

from corehq.apps.tzmigration.timezonemigration import MISSING
from corehq.blobs import get_blob_db
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.models import (
    Attachment,
    XFormInstanceSQL,
    XFormOperationSQL,
)
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
        assert kind == "CommCareCase", (kind, case_id)
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
    case_diffs = [d.json_diff for d in diffs if d.kind != "stock state"]
    try:
        couch_case = get_couch_case(case_id)
    except CaseNotFound:
        raise CannotPatch(case_diffs)
    assert couch_case.domain == get_domain(), (couch_case, get_domain())
    case = PatchCase(couch_case, case_diffs)
    form = PatchForm(case)
    process_patch(form)
    patch_ledgers([d for d in diffs if d.kind == "stock state"])


def patch_ledgers(diffs):
    if diffs:
        # TODO implement ledger patch
        raise CannotPatch([d.json_diff for d in diffs])


def aslist(generator_func):
    @wraps(generator_func)
    def wrapper(*args, **kw):
        return list(generator_func(*args, **kw))
    return wrapper


@attr.s(hash=False)
class PatchCase:
    case = attr.ib()
    diffs = attr.ib()

    def __attrs_post_init__(self):
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
        return (self.case.closed
            and any(d.path == ["closed"] and not d.new_value for d in self.diffs))

    def dynamic_case_properties(self):
        return self._dynamic_properties

    @property
    @memoized
    @aslist
    def indices(self):
        diffs = [d for d in self.diffs if d.path[0] == "indices"]
        if not diffs:
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
        updates = self._case._updates
        case_block = get_case_xml(self._case, updates, version='2.0')
        diff_block = get_diff_block(self._case)
        return render_to_string('hqcase/xml/case_block.xml', {
            'xmlns': self.xmlns,
            'case_block': case_block.decode('utf-8') + diff_block,
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
        "diffs": [
            {
                "path": diff.path,
                "old": diff.old_value,  # omitted if old_value is MISSING
                "new": diff.new_value,  # omitted if new_value is MISSING
                "patch": true if patched else false
                "reason": "...",  # omitted if reason for change is unknown
            },
            ...
        ]
    }
    ```
    """
    diffs = [diff_to_json(d) for d in sorted(case.diffs, key=lambda d: d.path)]
    data = {"case_id": case.case_id, "diffs": diffs}
    return f"<diff>{escape(json.dumps(data))}</diff>"


def diff_to_json(diff, new_value=None):
    assert diff.old_value is not MISSING or diff.new_value is not MISSING, diff
    obj = {"path": list(diff.path), "patch": is_patchable(diff)}
    if diff.old_value is not MISSING:
        obj["old"] = diff.old_value
    if diff.new_value is not MISSING:
        obj["new"] = diff.new_value if new_value is None else new_value
    if getattr(diff, "reason", ""):
        obj["reason"] = diff.reason
    return obj


def is_patchable(diff):
    return diff.path[0] not in UNPATCHABLE_PROPS


class CannotPatch(Exception):

    def __init__(self, json_diffs):
        super().__init__(repr(json_diffs))
        self.diffs = json_diffs


def is_missing_in_sql(diffs):
    diff = diffs[0]
    return (
        len(diffs) == 1
        and diff.diff_type == "missing"
        and diff.path == ['*']
        and diff.old_value is not MISSING
        and diff.new_value is MISSING
    )
