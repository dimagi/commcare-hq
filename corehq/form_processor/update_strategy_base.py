from abc import ABCMeta, abstractproperty


class UpdateStrategy(object):
    __metaclass__ = ABCMeta

    @abstractproperty
    def case_implementation_class(self):
        pass

    def __init__(self, case):
        self.case = case

    @classmethod
    def case_from_case_update(cls, case_update):
        """
        Create a case object from a case update object.
        """
        assert not case_update.xform.is_deprecated  # you should never be able to create a case from a deleted update
        case = cls.case_implementation_class()
        case.case_id = case_update.id

        case.modified_on = case_update.guess_modified_on()

        # attach domain and export tag
        case.domain = case_update.xform.domain

        # apply initial updates, if present
        cls(case).update_from_case_update(case_update)
        return case

    @abstractproperty
    def update_from_case_update(self, case_update, other_forms=None):
        pass
