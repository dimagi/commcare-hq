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