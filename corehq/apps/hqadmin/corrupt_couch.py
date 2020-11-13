"""Utilities for assessing and repairing CouchDB corruption"""
import logging
from collections import defaultdict
from itertools import chain
from urllib.parse import urljoin, urlparse, urlunparse

import attr
from couchdbkit import Database
from dateutil.parser import parser as parse_date
from django.conf import settings
from memoized import memoized

from auditcare.models import AuditEvent
from casexml.apps.case.models import CommCareCase
from couchforms.models import XFormInstance
from custom.m4change.models import FixtureReportResult
from dimagi.utils.parsing import json_format_datetime

from corehq.apps.app_manager.models import Application
from corehq.apps.fixtures.models import FixtureDataType
from corehq.apps.userreports.models import ReportConfiguration
from corehq.apps.users.models import CommCareUser
from corehq.apps.domain.models import Domain
from corehq.motech.repeaters.models import Repeater
from corehq.util.couch_helpers import NoSkipArgsProvider
from corehq.util.pagination import ResumableFunctionIterator

log = logging.getLogger(__name__)
COUCH_NODE_PORT = 15984
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


def count_missing_ids(*args, repair=False):
    def log_result(rec):
        repaired = f" repaired={rec.repaired}" if repair else ""
        log.info(
            f"  {rec.doc_type}:{repaired} missing={len(rec.missing)} "
            f"tries=(avg: {rec.avg_tries}, max: {rec.max_tries})"
        )

    doc_type = None
    rec = None
    results = defaultdict(Result)
    for doc_type, (missing, tries, repaired) in iter_missing_ids(*args, repair):
        if rec and doc_type != rec.doc_type:
            log_result(rec)
            results.pop(doc_type, None)
        rec = results[doc_type]
        rec.doc_type = doc_type
        rec.missing.update(missing)
        rec.tries.append(tries)
        rec.repaired += repaired
    if rec:
        log_result(rec)
    else:
        log.info("no documents found")


@attr.s
class Result:
    doc_type = attr.ib(default=None)
    missing = attr.ib(factory=set)
    tries = attr.ib(factory=list)
    repaired = attr.ib(default=0)

    @property
    def max_tries(self):
        return max(self.tries) if self.tries else 0

    @property
    def avg_tries(self):
        return round(sum(self.tries) / len(self.tries), 2) if self.tries else 0


def iter_missing_ids(min_tries, domain, doc_name="ALL", view_range=None, repair=False):
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
        db = CouchCluster(group["type"].get_db())
        domain_name = domain if group.get("use_domain") else None
        for doc_type in get_doc_types(group):
            params = iteration_parameters(db, doc_type, domain_name, view_range, group)
            missing_results = _iter_missing_ids(db, min_tries, *params, repair)
            try:
                for rec in missing_results:
                    yield doc_type, rec["missing_info"]
            finally:
                missing_results.discard_state()


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


def _iter_missing_ids(db, min_tries, resume_key, view_name, view_params, repair):
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
        missing, tries = find_missing_ids(get_doc_ids, min_tries=min_tries)
        if last_result is None:
            assert not missing
            return []
        if missing and repair:
            missing, tries2, repaired = repair_couch_docs(db, missing, get_doc_ids, min_tries)
            tries += tries2
        else:
            repaired = 0
        log.debug(f"{len(missing)}/{tries} start={view_kwargs['startkey']}")
        last_result["missing_info"] = missing, tries, repaired
        return [last_result]

    args_provider = NoSkipArgsProvider(view_params)
    return ResumableFunctionIterator(resume_key, data_function, args_provider, item_getter=None)


def repair_couch_docs(db, missing, get_doc_ids, min_tries):
    total_tries = 0
    to_repair = len(missing)
    max_repairs = min_tries
    for n in range(max_repairs):
        for doc_id in missing:
            db.repair(doc_id)
        missing, tries = find_missing_ids(get_doc_ids, min_tries=min_tries)
        total_tries += tries
        log.debug(f"repaired {to_repair - len(missing)} of {to_repair}")
        if not missing:
            break
    return missing, total_tries, to_repair - len(missing)


def iteration_parameters(db, doc_type, domain, view_range, group, chunk_size=1000):
    if "view" in group:
        view_name = group["view"]
        start = end = "-"
        assert doc_type is None, doc_type
        if domain is not None:
            startkey = [domain]
            endkey = [domain]
        else:
            startkey = []
            endkey = []
    elif domain is not None and doc_type is not None:
        view_name = 'by_domain_doc_type_date/view'
        startkey = [domain, doc_type]
        endkey = [domain, doc_type]
    elif doc_type is not None:
        view_name = 'all_docs/by_doc_type'
        startkey = [doc_type]
        endkey = [doc_type]
    else:
        view_name = 'all_docs/by_doc_type'
        startkey = []
        endkey = []
    if view_range is not None:
        assert domain or doc_type, (domain, doc_type)
        if group.get("date_range"):
            assert domain and doc_type and view_name == 'by_domain_doc_type_date/view', \
                (domain, doc_type, view_name, view_range)
            view_range = [json_format_datetime(parse_date(x)) for x in view_range]
        start, end = view_range
        startkey.append(start)
        endkey.append(end)
    else:
        start = end = "-"
    if startkey == endkey:
        endkey.append({})

    view_params = {
        'startkey': startkey,
        'endkey': endkey,
        'limit': chunk_size,
        'include_docs': False,
        'reduce': False,
    }
    resume_key = f"{db.dbname}.{domain}.{doc_type}.{start}-{end}"
    return resume_key, view_name, view_params


def find_missing_ids(get_doc_ids, min_tries, limit=None):
    """Find missing ids

    Given a function that is expected to always return the same set of
    unique ids, find all ids that are missing from some result sets.

    Returns a tuple `(missing_ids, tries)`
    """
    if min_tries < 2:
        raise ValueError("min_tries must be greater than 1")
    limit = limit or min_tries * 20
    min_tries -= 1
    missing = set()
    all_ids = set()
    no_news = 1
    for tries in range(limit):
        next_ids = get_doc_ids()
        if all_ids:
            miss = next_ids ^ all_ids
            if any(x not in missing for x in miss):
                no_news = 1
                missing.update(miss)
                all_ids.update(miss)
        else:
            all_ids.update(next_ids)
        if no_news > min_tries:
            return missing, tries + 1
        no_news += 1
    log.warning(f"still finding new missing docs after {limit} queries")
    return missing, limit


@attr.s
class CouchCluster:
    db = attr.ib()

    @property
    def dbname(self):
        return self.db.dbname

    @property
    @memoized
    def _node_dbs(self):
        return _get_couch_node_databases(self.db)

    def repair(self, doc_id):
        for node in self._node_dbs:
            node.get(doc_id)

    def view(self, *args, **kw):
        return self.db.view(*args, **kw)


def _get_couch_node_databases(db, node_port=COUCH_NODE_PORT):
    def node_url(proxy_url, node):
        return urlunparse(proxy_url._replace(netloc=f'{auth}@{node}:{node_port}'))

    resp = db.server._request_session.get(urljoin(db.server.uri, '/_membership'))
    resp.raise_for_status()
    membership = resp.json()
    nodes = [node.split("@")[1] for node in membership["cluster_nodes"]]
    proxy_url = urlparse(settings.COUCH_DATABASE)._replace(path=f"/{db.dbname}")
    auth = proxy_url.netloc.split('@')[0]
    return [Database(node_url(proxy_url, node)) for node in nodes]
