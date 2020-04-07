import logging
from datetime import datetime
from functools import partial
from uuid import uuid4

from django.template.loader import render_to_string

import attr
from memoized import memoized

from casexml.apps.phone.xml import get_case_xml
from dimagi.utils.couch.database import retry_on_couch_error
from dimagi.utils.parsing import json_format_datetime

from corehq.blobs import get_blob_db
from corehq.form_processor.backends.couch.dbaccessors import CaseAccessorCouch
from corehq.form_processor.models import (
    Attachment,
    XFormInstanceSQL,
    XFormOperationSQL,
)
from corehq.util.metrics import metrics_counter

from .casediff import get_domain
from .casedifftool import format_diffs
from .couchsqlmigration import get_case_and_ledger_updates, save_migrated_models
from .statedb import Change
from .util import retry_on_sql_error

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
        pending_diffs.append(case_id)
    return pending_diffs


def patch_case(case_id, diffs):
    case_diffs = [d for d in diffs if d.kind != "stock state"]
    couch_case = get_couch_case(case_id)
    assert couch_case.domain == get_domain(), (couch_case, get_domain())
    case = PatchCase(couch_case, case_diffs)
    form = PatchForm(case)
    process_patch(form)
    patch_ledgers([d for d in diffs if d.kind == "stock state"])


def patch_ledgers(diffs):
    if diffs:
        raise NotImplementedError


@attr.s
class PatchCase:
    case = attr.ib()
    diffs = attr.ib()
    indices = attr.ib(factory=list, init=False)
    case_attachments = attr.ib(factory=list, init=False)
    IGNORE_PROPS = {"xform_ids"}

    def __attrs_post_init__(self):
        self._updates = []
        if not all(isinstance(d, Change) for d in self.diffs):
            raise CannotPatch([d.json_diff for d in self.diffs])

    def __getattr__(self, name):
        return getattr(self.case, name)

    def dynamic_case_properties(self):
        props = {}
        ignore = self.IGNORE_PROPS
        for planning_diff in self.diffs:
            diff = planning_diff.json_diff
            path = diff.path
            if path[0] in ignore:
                continue
            raise CannotPatch([diff])
        return props


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
        return render_to_string('hqcase/xml/case_block.xml', {
            'xmlns': self.xmlns,
            'case_block': case_block.decode('utf-8'),
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
    save_sql_form(sql_form, case_stock_result)


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


class CannotPatch(Exception):

    def __init__(self, json_diffs):
        super().__init__(repr(json_diffs))
        self.diffs = json_diffs


@retry_on_couch_error
def get_couch_case(case_id):
    return CaseAccessorCouch.get_case(case_id)


@retry_on_sql_error
def save_sql_form(sql_form, case_stock_result):
    save_migrated_models(sql_form, case_stock_result)
