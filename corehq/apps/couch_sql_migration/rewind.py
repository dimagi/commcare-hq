import json
import logging
import re
import sys
from datetime import datetime, timedelta

import attr
from couchdbkit.exceptions import ResourceNotFound

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
        stats = rw.stats
        received_on = None
        try:
            for received_on in rw:
                if stats.total_docs > offset:
                    rw.save_state(received_on)
                    break
                if datetime.utcnow() > next_status:
                    log.info(str(stats))
                    next_status = datetime.utcnow() + status_interval
                    stats.reset()
        except KeyboardInterrupt:
            log.warn("interrupted")
            if received_on is not None:
                if input("save state (Y/n) ").lower() in ['y', '']:
                    rw.save_state(received_on)
                else:
                    log.info("state discarded (received_on=%s)", received_on)


@attr.s
class IterationState:
    statedb = attr.ib()
    domain = attr.ib()
    doc_type = attr.ib()

    def __attrs_post_init__(self):
        migration_id = self.statedb.unique_id
        resume_key = "%s.%s.%s" % (self.domain, self.doc_type, migration_id)
        self.itr = ResumableFunctionIterator(resume_key, None, None)

    @property
    def value(self):
        return self.itr.state.to_json()

    def backup_resume_state(self, value):
        """Attempt to save iteration state in state db

        :param value: iteration state dict. See `self.value`
        :returns: resume key if saved else `None`
        """
        assert isinstance(value, dict), value
        key = f"resume-{value['timestamp']}"
        pretty_value = json.dumps(value, indent=2)
        log.info("saving resume state with key=%s : %s", key, pretty_value)
        old = self.statedb.get(key)
        if old is None:
            self.statedb.set(key, value)
            log.info("saved.")
        elif old != value:
            log.warn("NOT SAVED! refusing to overwrite:\n%s", old)
            return None
        return key

    def restore_resume_state(self, key):
        """Attempt to restore resume state represented by key

        :returns: true if restored else false
        """
        new_state = self.statedb.get(key)
        if new_state is None:
            return False
        if "_rev" in self.value:
            backup_key = self.backup_resume_state(self.value)
            if backup_key is None:
                return False
        log.info("restoring iteration state: %s", new_state)
        self.itr._save_state_json(new_state)
        return True

    def drop_from_couch(self):
        """Delete resume state from Couch"""
        try:
            self.itr.couch_db.delete_doc(self.itr.iteration_id)
        except ResourceNotFound:
            pass


@attr.s
class Rewinder(IterationState):
    move_to = attr.ib()

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
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

    def resume_rewind(self, match):
        self.offset = None
        ok = self.restore_resume_state(self.move_to)
        if not ok:
            sys.exit(1, "resume state not found")

    def case_rewind(self, match):
        self.offset = int(match.group(1))
        self.stats = FormStats()

    def __iter__(self):
        def data_function(**view_kwargs):
            return couch_db.view('by_domain_doc_type_date/view', **view_kwargs)

        log.info("preparing to rewind: %s", self.move_to)
        state_json = self.value
        if not self.backup_resume_state(state_json):
            return
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
                yield get_received_on(result["doc"], self.stats)
            try:
                args, kwargs = args_provider.get_next_args(results[-1], *args, **kwargs)
            except StopIteration:
                break

    def save_state(self, received_on):
        state = self.itr.state
        startkey = state.kwargs["startkey"]
        assert len(startkey) == 3, startkey
        assert isinstance(startkey[-1], type(received_on)), (startkey, received_on)
        startkey[-1] = received_on
        assert state.kwargs["startkey"] is startkey, (state.kwargs, startkey)
        state.kwargs.pop("startkey_docid")
        state.timestamp = datetime.utcnow()
        key = self.backup_resume_state(state.to_json())
        if key:
            log.info("restore with: rewind --to=%s", key)


def get_received_on(doc, stats):
    form = XFormInstance.wrap(doc)
    case_ids = get_case_ids(form)
    stats.update(len(case_ids))
    return form.received_on


@attr.s
class FormStats:
    forms = attr.ib(default=0)
    cases = attr.ib(default=0)
    max_cases = attr.ib(default=0)
    total_forms = attr.ib(default=0)
    total_docs = attr.ib(default=0)

    def update(self, n_cases):
        self.forms += 1
        self.cases += n_cases
        if self.max_cases < n_cases:
            self.max_cases = n_cases
        self.total_forms += 1
        self.total_docs += n_cases

    def reset(self):
        self.forms = 0
        self.cases = 0
        self.max_cases = 0

    @property
    def avg_cases(self):
        return (self.cases / self.forms) if self.forms else 0

    def __str__(self):
        return (
            f"{self.total_docs} cases, "
            f"{self.total_forms} forms, "
            f"(batch: f={self.forms}, c={self.cases}, "
            f"avg={self.avg_cases:.1f}, "
            f"max={self.max_cases})"
        )
