from abc import ABCMeta, abstractproperty
from datetime import datetime

from dimagi.utils import parsing


class UpdateStrategy(object):
    __metaclass__ = ABCMeta

    @abstractproperty
    def case_implementation_class(self):
        pass

    def __init__(self, case):
        self.case = case

    @classmethod
    def case_from_case_update(cls, case_update, xformdoc):
        """
        Create a case object from a case update object.
        """
        assert not xformdoc.is_deprecated  # you should never be able to create a case from a deleted update
        case = cls.case_implementation_class()
        case.case_id = case_update.id

        if case_update.modified_on_str:
            case.modified_on = parsing.string_to_utc_datetime(case_update.modified_on_str)
        else:
            case.modified_on = datetime.utcnow()

        # attach domain and export tag
        case.domain = xformdoc.domain

        # apply initial updates, if present
        cls(case).update_from_case_update(case_update, xformdoc)
        return case

    @abstractproperty
    def update_from_case_update(self, case_update, xformdoc, other_forms=None):
        pass
