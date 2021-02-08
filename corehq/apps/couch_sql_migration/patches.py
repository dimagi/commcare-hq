import logging
import re
from contextlib import contextmanager

from memoized import memoized

import casexml.apps.case.xform as case_xform
from casexml.apps.case.exceptions import IllegalCaseId
from casexml.apps.case.xform import has_case_id
from couchforms.models import XFormInstance
from dimagi.ext.jsonobject import DateTimeProperty

import corehq.form_processor.parsers.ledgers.form as ledger_form
from corehq.apps.change_feed.producer import ChangeProducer
from corehq.form_processor.backends.sql.update_strategy import PROPERTY_TYPE_MAPPING
from corehq.form_processor.exceptions import MissingFormXml

from .diff import MALFORMED_DATE
from .json2xml import convert_form_to_xml

log = logging.getLogger(__name__)


@contextmanager
def migration_patches():
    with patch_case_property_validators(), \
            patch_XFormInstance_get_xml(), \
            patch_DateTimeProperty_wrap(), \
            patch_case_date_modified_fixer(), \
            patch_illegal_ledger_case_id(), \
            patch_ledger_balance_without_product(), \
            patch_kafka():
        yield


@contextmanager
def patch_case_property_validators():
    def truncate_255(value):
        return value[:255]

    original = PROPERTY_TYPE_MAPPING.copy()
    PROPERTY_TYPE_MAPPING.update(
        name=truncate_255,
        type=truncate_255,
        owner_id=truncate_255,
        external_id=truncate_255,
    )
    try:
        yield
    finally:
        PROPERTY_TYPE_MAPPING.update(original)


@contextmanager
def patch_case_date_modified_fixer():
    def has_case_id_and_valid_date_modified(case_block):
        has_case = has_case_id(case_block)
        if has_case:
            datemod = case_block.get('@date_modified')
            if isinstance(datemod, str) and MALFORMED_DATE.match(datemod):
                # fix modified date so subsequent validation (immediately
                # after this function call) does not fail
                if len(datemod) == 10:
                    # format: MM-DD-YYYY -> YYYY-MM-DD
                    case_block["@date_modified"] = datemod[6:] + "-" + datemod[:5]
                elif len(datemod) == 11:
                    # format: YYYY-MM-0DD -> YYYY-MM-DD
                    assert datemod[8] == "0", datemod
                    case_block["@date_modified"] = datemod[:8] + datemod[9:]
                elif len(datemod) == 17:
                    # MM/DD/YY HH:MM:SS -> YYYY-MM-DD HH:MM:SS
                    old = datemod.replace("/", "-")
                    case_block["@date_modified"] = f"20{old[6:8]}-{old[:5]} {old[9:]}"
        return has_case

    with patch(case_xform, "has_case_id", has_case_id_and_valid_date_modified):
        yield


@contextmanager
def patch_DateTimeProperty_wrap():
    def wrap(self, value):
        if isinstance(value, str):
            match = weird_utc_date.match(value)
            if match:
                value = f"{match.group(1)}Z"
        return real_wrap(self, value)

    weird_utc_date = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)\+00:00Z$")
    with patch(DateTimeProperty, "_wrap", wrap) as real_wrap:
        yield


@contextmanager
def patch_XFormInstance_get_xml():
    @memoized
    def get_xml(self):
        try:
            return self._unsafe_get_xml()
        except MissingFormXml as err:
            try:
                data = self.to_json()
            except Exception:
                raise err
            return convert_form_to_xml(data["form"]).encode('utf-8')

    if hasattr(XFormInstance, "_unsafe_get_xml"):
        # noop when already patched
        yield
    else:
        with patch(XFormInstance, "get_xml", get_xml) as unsafe_get_xml:
            XFormInstance._unsafe_get_xml = unsafe_get_xml
            try:
                yield
            finally:
                del XFormInstance._unsafe_get_xml


@contextmanager
def patch_kafka():
    def drop_change(self, topic, change_meta):
        doc_id = change_meta.document_id
        log.debug("kafka not publishing doc_id=%s to %s", doc_id, topic)

    with patch(ChangeProducer, "send_change", drop_change):
        yield


@contextmanager
def patch_illegal_ledger_case_id():
    def get_helpers(*args, **kw):
        try:
            yield from real_get_helpers(*args, **kw)
        except IllegalCaseId:
            pass  # ignore transfer with missing src and dest case_id

    method = "_get_transaction_helpers_from_transfer_instruction"
    with patch(ledger_form, method, get_helpers) as real_get_helpers:
        yield


@contextmanager
def patch_ledger_balance_without_product():
    def get_helpers(ledger_instruction):
        if not ledger_instruction.entry_id:
            return
        yield from real_get_helpers(ledger_instruction)

    method = "_get_transaction_helpers_from_balance_instruction"
    with patch(ledger_form, method, get_helpers) as real_get_helpers:
        yield


@contextmanager
def patch(obj, attr, new_value):
    old_value = getattr(obj, attr)
    setattr(obj, attr, new_value)
    try:
        yield old_value
    finally:
        setattr(obj, attr, old_value)
