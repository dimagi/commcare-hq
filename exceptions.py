from buildmanager.exceptions import FormValidationError

class FormReleaseError(FormValidationError):
    pass

class XFormConflictError(FormValidationError):
    pass