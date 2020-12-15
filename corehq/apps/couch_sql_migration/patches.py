import logging
import re
from contextlib import contextmanager

from memoized import memoized

import casexml.apps.case.xform as module
from casexml.apps.case.xform import has_case_id
from couchforms.models import XFormInstance
from dimagi.ext.jsonobject import DateTimeProperty

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

    module.has_case_id = has_case_id_and_valid_date_modified
    try:
        yield
    finally:
        module.has_case_id = has_case_id


@contextmanager
def patch_DateTimeProperty_wrap():
    def wrap(self, value):
        if isinstance(value, str):
            match = weird_utc_date.match(value)
            if match:
                value = f"{match.group(1)}Z"
        return real_wrap(self, value)

    weird_utc_date = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)\+00:00Z$")
    real_wrap = DateTimeProperty._wrap
    DateTimeProperty._wrap = wrap
    try:
        yield
    finally:
        DateTimeProperty._wrap = real_wrap


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
        return

    XFormInstance._unsafe_get_xml = XFormInstance.get_xml
    XFormInstance.get_xml = get_xml
    try:
        yield
    finally:
        XFormInstance.get_xml = XFormInstance._unsafe_get_xml
        del XFormInstance._unsafe_get_xml


@contextmanager
def patch_kafka():
    def drop_change(self, topic, change_meta):
        doc_id = change_meta.document_id
        log.debug("kafka not publishing doc_id=%s to %s", doc_id, topic)

    send_change = ChangeProducer.send_change
    ChangeProducer.send_change = drop_change
    try:
        yield
    finally:
        ChangeProducer.send_change = send_change
