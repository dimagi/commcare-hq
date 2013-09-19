
class CaseLogicException(Exception):
    """
    A custom exception for when our case logic goes awry.
    """
    pass


class IllegalCaseId(Exception):
    """
    Raise when someone tries to use a case_id for a doc
    that the caller should not have access to
    or is of the wrong case type
    """
    pass


class NoDomainProvided(Exception):
    pass


class RestoreException(Exception):
    """
    For stuff that goes wrong during restore
    """
    pass


class BadStateException(RestoreException):

    def __init__(self, expected, actual, case_ids, **kwargs):
        super(BadStateException, self).__init__(**kwargs)
        self.expected = expected
        self.actual = actual
        self.case_ids = case_ids

    def __str__(self):
        return "Phone state has mismatch. Expected %s but was %s. Cases: [%s]" % \
                (self.expected, self.actual, ", ".join(self.case_ids))
