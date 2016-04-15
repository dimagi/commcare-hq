from abc import ABCMeta, abstractmethod, abstractproperty
import six
from casexml.apps.case.exceptions import IllegalCaseId
from dimagi.utils.couch import release_lock
from corehq.form_processor.interfaces.processor import CaseUpdateMetadata


def _get_id_for_case(case):
    if isinstance(case, dict):
        return case['_id']
    return case.case_id


class AbstractCaseDbCache(six.with_metaclass(ABCMeta)):
    """
    A temp object we use to keep a cache of in-memory cases around
    so we can get the latest updates even if they haven't been saved
    to the database. Also provides some type checking safety.
    """

    @abstractproperty
    def case_model_classes(self):
        """
        :return: tuple of allowable classes
        """
        return ()

    @abstractproperty
    def case_update_strategy(self):
        return None

    def __init__(self, domain=None, strip_history=False, deleted_ok=False,
                 lock=False, wrap=True, initial=None, xforms=None):

        self._populate_from_initial(initial)
        self.domain = domain
        self.xforms = xforms if xforms is not None else []
        self.strip_history = strip_history
        self.deleted_ok = deleted_ok
        self.lock = lock
        self.wrap = wrap
        if self.lock and not self.wrap:
            raise ValueError('Currently locking only supports explicitly wrapping cases!')
        self.locks = []
        self._changed = set()

    def _populate_from_initial(self, initial_cases):
        if initial_cases:
            self.cache = {_get_id_for_case(case): case for case in initial_cases}
        else:
            self.cache = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for lock in self.locks:
            if lock:
                release_lock(lock, True)

    @abstractmethod
    def _validate_case(self, case):
        """Raise subclass of CommCareCaseError for invalid cases
        """
        pass

    def get(self, case_id):
        if not case_id:
            raise IllegalCaseId('case_id must not be empty')
        if case_id in self.cache:
            return self.cache[case_id]

        case = self._get_case(case_id)
        if case:
            self._validate_case(case)
            self.cache[case_id] = case
        return case

    @abstractmethod
    def _get_case(self, case_id):
        pass

    def set(self, case_id, case):
        assert isinstance(case, self.case_model_classes)
        self.cache[case_id] = case

    def in_cache(self, case_id):
        return case_id in self.cache

    def populate(self, case_ids):
        """
        Populates a set of IDs in the cache in bulk.
        Use this if you know you are going to need to access these later for performance gains.
        Does NOT overwrite what is already in the cache if there is already something there.
        """
        case_ids = list(set(case_ids) - set(self.cache.keys()))
        for case in self._iter_cases(case_ids):
            self.set(_get_id_for_case(case), case)

    @abstractmethod
    def _iter_cases(self, case_ids):
        pass

    def mark_changed(self, case):
        assert self.cache.get(case.case_id) is case
        self._changed.add(_get_id_for_case(case))

    def get_changed(self):
        return [self.cache[case_id] for case_id in self._changed]

    def clear_changed(self):
        self._changed = set()

    def get_cached_forms(self):
        """
        Get any in-memory forms being processed.
        """
        return {xform.form_id: xform for xform in self.xforms}

    @abstractmethod
    def get_cases_for_saving(self, now):
        pass

    def get_case_from_case_update(self, case_update, xform):
        """
        Gets or updates an existing case, based on a block of data in a
        submitted form.  Doesn't save anything. Returns a CaseUpdateMetadata object.
        """
        case = self.get(case_update.id)
        if case is None:
            case = self.case_update_strategy.case_from_case_update(case_update, xform)
            self.set(case.case_id, case)
            return CaseUpdateMetadata(case, is_creation=True, previous_owner_id=None)
        else:
            previous_owner = case.owner_id
            self.case_update_strategy(case).update_from_case_update(case_update, xform, self.get_cached_forms())
            return CaseUpdateMetadata(case, is_creation=False, previous_owner_id=previous_owner)

    def post_process_case(self, case, xform):
        pass

    @abstractmethod
    def get_reverse_indexed_cases(self, case_ids):
        pass

    def apply_action_intents(self, case, primary_intent, deprecation_intent=None):
        """
        Apply a CaseActionIntent object to the case.
        """
        # This is only used by ledger actions currently
        self.case_update_strategy(case).apply_action_intents(primary_intent, deprecation_intent)
