import logging
import re
import sys
from datetime import datetime, timedelta

import attr

from couchforms.models import XFormInstance

from corehq.util.couch_helpers import NoSkipArgsProvider
from corehq.util.pagination import ResumableFunctionIterator

from .asyncforms import get_case_ids

log = logging.getLogger(__name__)


def rewind_iteration_state(statedb, domain, move_to):
    doc_type = "XFormInstance"
    status_interval = timedelta(minutes=1)
    next_status = datetime.utcnow() - status_interval
    rw = Rewinder(statedb, domain, doc_type, move_to)
    if rw.offset:
        offset = rw.offset
        for n, item in enumerate(rw, start=1):
            if n > offset:
                rw.save_state(item)
                break
            if datetime.utcnow() > next_status:
                log.info("scanned %s docs", n)
                next_status = datetime.utcnow() + status_interval


@attr.s
class Rewinder:
    statedb = attr.ib()
    domain = attr.ib()
    doc_type = attr.ib()
    move_to = attr.ib()

    def __attrs_post_init__(self):
        for method, regex in [
            ("case_rewind", r"^case-(\d+)$"),
            ("resume_rewind", r"^resume-"),
        ]:
            match = re.search(regex, self.move_to)
            if match:
                getattr(self, method)(match)
                break
        else:
            raise NotImplementedError(self.move_to)
        migration_id = self.statedb.unique_id
        resume_key = "%s.%s.%s" % (self.domain, self.doc_type, migration_id)
        self.itr = ResumableFunctionIterator(resume_key, None, None, None)

    def resume_rewind(self, match):
        self.offset = None
        new_state = self.statedb.get(self.move_to)
        if new_state is None:
            sys.exit(1, "resume state not found")
        old_state = self.itr.state
        self._save_resume_state(old_state.to_json())
        log.info("restoring iteration state: %s", new_state)
        self.itr._save_state_json(new_state)

    def case_rewind(self, match):
        self.offset = int(match.group(1))

    def __iter__(self):
        def data_function(**view_kwargs):
            return couch_db.view('by_domain_doc_type_date/view', **view_kwargs)

        log.info("preparing to rewind: %s", self.move_to)
        state_json = self.itr.state.to_json()
        self._save_resume_state(state_json)
        couch_db = XFormInstance.get_db()
        args_provider = NoSkipArgsProvider({
            'startkey': state_json["kwargs"]["startkey"],
            'startkey_docid': state_json["kwargs"]["startkey_docid"],
            'endkey': [self.domain, self.doc_type],
            'descending': True,
            'limit': 1000,
            'include_docs': True,
            'reduce': False,
        })
        args, kwargs = args_provider.get_initial_args()
        while True:
            results = list(data_function(*args, **kwargs))
            results = args_provider.adjust_results(results, args, kwargs)
            if not results:
                break
            for result in results:
                yield from iter_case_items(result["doc"])
            try:
                args, kwargs = args_provider.get_next_args(results[-1], *args, **kwargs)
            except StopIteration:
                break

    def save_state(self, item):
        state = self.itr.state
        startkey = state.kwargs["startkey"]
        assert len(startkey) == 3, startkey
        startkey[-1] = item.form.received_on
        assert state.kwargs["startkey"] is startkey, (state.kwargs, startkey)
        state.kwargs.pop("startkey_docid")
        state.timestamp = datetime.utcnow()
        self._save_resume_state(state.to_json())

    def _save_resume_state(self, state_json):
        assert isinstance(state_json, dict), state_json
        key = f"resume-{state_json['timestamp']}"
        log.info("saving resume state. restore with: rewind --to=%s\n%s",
                 key, state_json)
        old = self.statedb.get(key)
        if old is None:
            self.statedb.set(key, state_json)
        elif old != state_json:
            log.warn("NOT SAVED! refusing to overwrite:\n%s", old)


def iter_case_items(doc):
    form = XFormInstance.wrap(doc)
    for case_id in get_case_ids(form):
        yield CaseItem(form, case_id)


@attr.s
class CaseItem:
    form = attr.ib()
    case_id = attr.ib()
