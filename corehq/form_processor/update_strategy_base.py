from __future__ import absolute_import
from __future__ import unicode_literals
from abc import ABCMeta, abstractproperty, abstractmethod
import six


class UpdateStrategy(six.with_metaclass(ABCMeta, object)):
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

        case.modified_on = case_update.guess_modified_on()

        # attach domain and export tag
        case.domain = xformdoc.domain

        # apply initial updates, if present
        cls(case).update_from_case_update(case_update, xformdoc)
        return case

    @abstractproperty
    def update_from_case_update(self, case_update, xformdoc, other_forms=None):
        pass

    @abstractmethod
    def apply_action_intents(self, primary_intent, deprecation_intent=None):
        pass
