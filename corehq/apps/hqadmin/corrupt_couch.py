"""Utilities for assessing and repairing CouchDB corruption"""
import logging
from collections import defaultdict
from itertools import chain

import attr

from auditcare.models import AuditEvent
from casexml.apps.case.models import CommCareCase
from corehq.apps.fixtures.models import FixtureDataType
from corehq.apps.userreports.models import ReportConfiguration
from corehq.motech.repeaters.models import Repeater
from couchforms.models import XFormInstance
from custom.m4change.models import FixtureReportResult
from dimagi.utils.parsing import json_format_datetime

from corehq.apps.app_manager.models import Application
from corehq.apps.users.models import CommCareUser
from corehq.apps.domain.models import Domain
from corehq.util.couch_helpers import NoSkipArgsProvider
from corehq.util.pagination import ResumableFunctionIterator

log = logging.getLogger(__name__)
DOC_TYPES_BY_NAME = {
    "forms": {
        "type": XFormInstance,
        "date_range": True,
        "use_domain": True,
        "doc_types": [
            'XFormInstance',
            'XFormArchived',
            'XFormDeprecated',
            'XFormDuplicate',
            'XFormError',
            'SubmissionErrorLog',
            'XFormInstance-Deleted',
            'HQSubmission',
        ],
    },
    "cases": {
        "type": CommCareCase,
        "use_domain": True,
        "doc_types": [
            "CommCareCase",
            "CommCareCase-Deleted",
        ],
    },
    "main": {
        "type": XFormInstance,
        "exclude_types": ["forms", "cases"],
    },
    "users": {
        "type": CommCareUser,
        "use_domain": True,
        "date_range": True,  # TODO will this work?
        "doc_types": [
            "CommCareUser",
            "WebUser",
        ],
    },
    "groups": {
        "type": CommCareUser,
        "use_domain": True,
        "exclude_types": ["users"],
    },
    "domains": {"type": Domain},
    "apps": {
        "type": Application,
        "use_domain": True,
    },
    "auditcare": {
        "type": AuditEvent,
        "use_domain": True,
        "view": "auditcare/all_events",
    },
    "fixtures": {
        "type": FixtureDataType,
        "use_domain": True
    },
    "m4change": {
        "type": FixtureReportResult,
        "view": "m4change/fixture_by_composite_key",
    },
    "receiver_wrapper_repeaters": {
        "type": Repeater,
        "use_domain": True,
        "view": "repeaters/repeaters",
    },
    "receiver_wrapper_repeat_records": {
        "type": Repeater,
        "use_domain": True,
        "view": "repeaters/repeat_records",
    },
    "meta": {
        "type": ReportConfiguration,
        "use_domain": True
    },
}


def count_missing_ids(*args):
    def log_result(rec):
        log.info(
            f"  {rec.doc_type}: missing={len(rec.missing)} "
            f"tries=(avg: {rec.avg_tries}, max: {rec.max_tries})"
        )

    doc_type = None
    rec = None
    results = defaultdict(Result)
    for doc_type, (missing, tries) in iter_missing_ids(*args):
        if rec and doc_type != rec.doc_type:
            log_result(rec)
            results.pop(doc_type, None)
        rec = results[doc_type]
        rec.doc_type = doc_type
        rec.missing.update(missing)
        rec.tries.append(tries)
    if rec:
        log_result(rec)
    else:
        log.info("no documents found")


@attr.s
class Result:
    doc_type = attr.ib(default=None)
    missing = attr.ib(factory=set)
    tries = attr.ib(factory=list)

    @property
    def max_tries(self):
        return max(self.tries) if self.tries else 0

    @property
    def avg_tries(self):
        return round(sum(self.tries) / len(self.tries), 2) if self.tries else 0


def iter_missing_ids(domain, doc_name="ALL", date_range=None):
    if doc_name == "ALL":
        groups = dict(DOC_TYPES_BY_NAME)
        if domain is not None:
            groups = {k: g for k, g in groups.items() if g.get("use_domain")}
        else:
            groups = {k: g for k, g in groups.items() if not g.get("use_domain")}
    else:
        groups = {doc_name: DOC_TYPES_BY_NAME[doc_name]}
        if domain is not None:
            if not groups[doc_name].get("use_domain"):
                raise ValueError(f"domain not supported with {doc_name!r}")
        else:
            if groups[doc_name].get("use_domain"):
                raise ValueError(f"domain required for {doc_name!r}")
    for name, group in groups.items():
        log.info("processing %s", name)
        db = group["type"].get_db()
        dates = date_range if group.get("date_range") else None
        domain_name = domain if group.get("use_domain") else None
        view = group.get("view")
        for doc_type in get_doc_types(group):
            itr = _iter_missing_ids(db, doc_type, domain_name, dates, view)
            try:
                for rec in itr:
                    yield doc_type, rec["missing_and_tries"]
            finally:
                itr.discard_state()


#def fix_missing_doc(doc_type, doc_id):
#    ...


def get_doc_types(group):
    if "exclude_types" in group:
        assert "doc_types" not in group, group
        excludes = set(chain.from_iterable(
            DOC_TYPES_BY_NAME[n]["doc_types"] for n in group["exclude_types"]
        ))
        db = group["type"].get_db()
        results = db.view("all_docs/by_doc_type", group_level=1)
        return [r["key"][0] for r in results if r["key"][0] not in excludes]
    return group.get("doc_types", [None])


def _iter_missing_ids(db, doc_type, domain, date_range, view, chunk_size=1000):
    def data_function(**view_kwargs):
        def get_doc_ids():
            results = list(db.view(view_name, **view_kwargs))
            if "limit" in view_kwargs and results:
                nonlocal last_result
                last_result = results[-1]
                replace_limit_with_endkey(view_kwargs, last_result)
            return {r["id"] for r in results}

        def replace_limit_with_endkey(view_kwargs, last_result):
            assert "endkey_docid" not in view_kwargs, view_kwargs
            view_kwargs.pop("limit")
            view_kwargs["endkey"] = last_result["key"]
            view_kwargs["endkey_docid"] = last_result["id"]

        last_result = None
        missing, tries = find_missing_ids(get_doc_ids)
        if last_result is None:
            assert not missing
            return []
        last_result["missing_and_tries"] = missing, tries
        return [last_result]

    if view is not None:
        view_name = view
        start = end = "-"
        assert date_range is None, date_range
        assert doc_type is None, doc_type
        if domain is not None:
            startkey = [domain]
            endkey = [domain, {}]
        else:
            startkey = []
            endkey = [{}]
    elif date_range is not None:
        assert domain is not None
        assert doc_type is not None
        view_name = 'by_domain_doc_type_date/view'
        start, end = date_range
        startkey = [domain, doc_type, json_format_datetime(start)]
        endkey = [domain, doc_type, json_format_datetime(end)]
    elif domain is not None and doc_type is not None:
        view_name = 'by_domain_doc_type_date/view'
        start = end = "-"
        startkey = [domain, doc_type]
        endkey = [domain, doc_type, {}]
    elif doc_type is not None:
        view_name = 'all_docs/by_doc_type'
        start = end = "-"
        startkey = [doc_type]
        endkey = [doc_type, {}]
    else:
        view_name = 'all_docs/by_doc_type'
        start = end = "-"
        startkey = []
        endkey = [{}]

    resume_key = f"{db.dbname}.{domain}.{doc_type}.{start}-{end}"
    args_provider = NoSkipArgsProvider({
        'startkey': startkey,
        'endkey': endkey,
        'limit': chunk_size,
        'include_docs': False,
        'reduce': False,
    })
    return ResumableFunctionIterator(resume_key, data_function, args_provider, item_getter=None)


def find_missing_ids(get_doc_ids, min_tries=5, limit=100):
    """Find missing ids

    Given a function that is expected to always return the same set of
    unique ids, find all ids that are missing from some result sets.

    Returns a tuple `(missing_ids, tries)
    """
    min_tries -= 1
    missing = set()
    all_ids = set()
    no_news = 0
    for tries in range(limit):
        next_ids = get_doc_ids()
        if all_ids:
            miss = next_ids ^ all_ids
            if any(x not in missing for x in miss):
                no_news = 0
                missing.update(miss)
                all_ids.update(miss)
        else:
            all_ids.update(next_ids)
        if no_news > min_tries:
            return missing, tries + 1
        no_news += 1
    log.warning("still finding new missing docs after 100 queries")
    return missing, 100
