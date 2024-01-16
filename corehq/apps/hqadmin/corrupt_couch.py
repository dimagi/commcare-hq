"""Utilities for assessing and repairing CouchDB corruption"""
import logging
from collections import defaultdict
from itertools import islice
from json.decoder import JSONDecodeError
from urllib.parse import urljoin, urlparse, urlunparse

import attr
from couchdbkit import Database
from couchdbkit.exceptions import ResourceNotFound
from dateutil.parser import parse as parse_date
from django.conf import settings
from memoized import memoized

from dimagi.utils.chunked import chunked
from dimagi.utils.couch.bulk import BulkFetchException
from dimagi.utils.couch.database import retry_on_couch_error
from dimagi.utils.parsing import json_format_datetime

from corehq.apps.app_manager.models import Application
from corehq.apps.userreports.models import ReportConfiguration
from corehq.apps.users.models import CommCareUser
from corehq.apps.domain.models import Domain
from corehq.toggles.models import Toggle
from corehq.util.couch_helpers import NoSkipArgsProvider
from corehq.util.pagination import ResumableFunctionIterator

log = logging.getLogger(__name__)
COUCH_NODE_PORT = 15984
DOC_TYPES_BY_NAME = {
    "main": {
        "type": Toggle,
        "exclude_types": {
            'XFormInstance',
            'XFormArchived',
            'XFormDeprecated',
            'XFormDuplicate',
            'XFormError',
            'SubmissionErrorLog',
            'XFormInstance-Deleted',
            'HQSubmission',
            "CommCareCase",
            "CommCareCase-Deleted",
        },
    },
    "users": {
        "type": CommCareUser,
        "use_domain": True,
    },
    "domains": {"type": Domain},
    "apps": {
        "type": Application,
        "use_domain": True,
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


def repair_missing_ids(doc_name, missing_ids_file, line_range, min_tries):
    def get_missing(doc_ids):
        @retry_on_couch_error
        def get_doc_ids():
            try:
                results = list(db.view("_all_docs", **view_kwargs))
            except JSONDecodeError as err:
                raise BulkFetchException(f"{type(err).__name__}: {err}")  # retry
            try:
                return {r["id"] for r in results}
            except KeyError as err:
                raise BulkFetchException(f"{type(err).__name__}: {err}")  # retry

        view_kwargs = {
            "keys": list(doc_ids),
            "include_docs": False,
            "reduce": False,
        }
        return find_missing_ids(get_doc_ids, min_tries)[0]

    db = CouchCluster(DOC_TYPES_BY_NAME[doc_name]["type"].get_db())
    with open(missing_ids_file, encoding="utf-8") as missing_ids:
        total = sum(1 for id in missing_ids if id.strip())
        missing_ids.seek(0)
        missing_ids = (id.strip() for id in missing_ids if id.strip())
        if any(line_range):
            start, stop = line_range
            total = (stop or total) - start
            log.info("scanning %s ids on lines %s..%s", total, start, stop or "")
            missing_ids = islice(missing_ids, start, stop)
        repaired = 0
        for doc_ids in chunked(missing_ids, 100, list):
            missing = None
            for x in range(min_tries):
                for doc_id in doc_ids:
                    log.debug("repairing %s", doc_id)
                    db.repair(doc_id)
                missing = get_missing(doc_ids)
                repaired += len(doc_ids) - len(missing)
                log.info("repaired %s of %s missing docs", repaired, total)
                if not missing:
                    break
                doc_ids = missing
            if missing:
                log.warning("could not repair %s missing docs", len(missing))
                print("\n".join(sorted(missing)))
    log.info("repaired %s of %s missing docs", repaired, total)


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


def iter_missing_ids(min_tries, params, repair=False):
    if params.doc_name == "ALL":
        assert not params.doc_type, params
        groups = dict(DOC_TYPES_BY_NAME)
        if params.domain is not None:
            groups = {k: g for k, g in groups.items() if g.get("use_domain")}
        else:
            groups = {k: g for k, g in groups.items() if not g.get("use_domain")}
    else:
        groups = {params.doc_name: DOC_TYPES_BY_NAME[params.doc_name]}
    for name, group in groups.items():
        if params.doc_type:
            group = dict(group, doc_types=[params.doc_type])
        log.info("processing %s", name)
        db = CouchCluster(group["type"].get_db())
        domain_name = params.domain if group.get("use_domain") else None
        for doc_type in get_doc_types(group):
            iter_params = iteration_parameters(
                db, doc_type, domain_name, params.view_range, group)
            missing_results = _iter_missing_ids(db, min_tries, *iter_params, repair)
            try:
                for rec in missing_results:
                    yield doc_type, rec["missing_info"]
            finally:
                missing_results.discard_state()


def get_doc_types(group):
    if "exclude_types" in group:
        assert "doc_types" not in group, group
        excludes = group["exclude_types"]
        db = group["type"].get_db()
        results = db.view("all_docs/by_doc_type", group_level=1)
        return [r["key"][0] for r in results if r["key"][0] not in excludes]
    return group.get("doc_types", [None])


def _iter_missing_ids(db, min_tries, resume_key, view_name, view_params, repair):
    def data_function(**view_kwargs):
        @retry_on_couch_error
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
            log.debug("no results %s - %s", view_kwargs['startkey'], view_kwargs['endkey'])
            assert not missing
            return []
        if missing and repair:
            missing, tries2, repaired = repair_couch_docs(db, missing, get_doc_ids, min_tries)
            tries += tries2
        else:
            repaired = 0
        log.debug(f"{len(missing)}/{tries} start={view_kwargs['startkey']} {missing or ''}")
        last_result["missing_info"] = missing, tries, repaired
        return [last_result]

    args_provider = NoSkipArgsProvider(view_params)
    return ResumableFunctionIterator(resume_key, data_function, args_provider)


def repair_couch_docs(db, missing, get_doc_ids, min_tries):
    total_tries = 0
    to_repair = len(missing)
    max_repairs = min_tries
    for n in range(max_repairs):
        for doc_id in missing:
            db.repair(doc_id)
        repaired = missing
        missing, tries = find_missing_ids(get_doc_ids, min_tries=min_tries)
        total_tries += tries
        if log.isEnabledFor(logging.DEBUG):
            repaired -= missing
            log.debug(f"repaired {to_repair - len(missing)} of {to_repair}: {repaired or ''}")
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
    elif domain is not None:
        view_name = 'by_domain_doc_type_date/view'
        if doc_type is not None:
            startkey = [domain, doc_type]
            endkey = [domain, doc_type]
        else:
            startkey = [domain]
            endkey = [domain]
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

    @retry_on_couch_error
    def repair(self, doc_id):
        for node in self._node_dbs:
            try:
                node.get(doc_id)
            except ResourceNotFound:
                pass

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
