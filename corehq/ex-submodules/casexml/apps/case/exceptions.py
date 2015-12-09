class CommCareCaseError(Exception):
    """
    Parent type for all case errors
    """
    pass


class CaseLogicException(CommCareCaseError):
    """
    A custom exception for when our case logic goes awry.
    """
    pass


class IllegalCaseId(CommCareCaseError):
    """
    Raise when someone tries to use a case_id for a doc
    that the caller should not have access to
    or is of the wrong case type
    """
    pass


class UsesReferrals(CommCareCaseError):
    pass


class NoDomainProvided(CommCareCaseError):
    pass


class ReconciliationError(CommCareCaseError):
    """
    Raise when a precondition fails for an attempted case reconciliation
    """
    pass


class MissingServerDate(ReconciliationError):
    pass


class VersionNotSupported(CommCareCaseError):
    pass


class PhoneDateValueError(CommCareCaseError):
    pass
