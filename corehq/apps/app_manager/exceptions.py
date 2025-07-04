from corehq.apps.app_manager.const import APP_V2


class AppManagerException(Exception):
    pass


class VersioningError(AppManagerException):
    """For errors that violate the principles of versioning in ApplicationBase"""
    pass


class ModuleNotFoundException(AppManagerException, IndexError):
    pass


class FormNotFoundException(AppManagerException, IndexError):
    pass


class IncompatibleFormTypeException(AppManagerException):
    pass


class AddOnNotFoundException(AppManagerException, IndexError):
    pass


class AppEditingError(AppManagerException):
    pass


class ModuleIdMissingException(AppManagerException):
    pass


class RearrangeError(AppEditingError):
    pass


class XFormException(AppManagerException):
    pass


class CaseError(XFormException):
    pass


class ScheduleError(XFormException):
    pass


class XFormValidationFailed(XFormException):
    """Unable to communicate with validation service or validation service errored"""
    pass


class XFormValidationError(XFormException):

    def __init__(self, fatal_error, version=APP_V2, validation_problems=None):
        self.fatal_error = fatal_error
        self.version = version
        self.validation_problems = validation_problems or []

    def __str__(self):
        fatal_error_text = self.format_v1(self.fatal_error)
        ret = "Validation Error%s" % (': %s' % fatal_error_text if fatal_error_text else '')
        problems = [problem for problem in self.validation_problems if problem['message'] != self.fatal_error]
        if problems:
            ret += "\n\nMore information:"
            for problem in problems:
                ret += "\n{type}: {msg}".format(type=problem['type'].title(), msg=problem['message'])
        return ret

    def format_v1(self, msg):
        if self.version != '1.0':
            return msg
        # Don't display the first two lines which say "Parsing form..." and 'Title: "{form_name}"'
        #
        # ... and if possible split the third line that looks like
        # e.g. "org.javarosa.xform.parse.XFormParseException: Select question has no choices"
        # and just return the undecorated string
        #
        # ... unless the first line says
        message_lines = str(msg).split('\n')[2:]
        if len(message_lines) > 0 and ':' in message_lines[0] and 'XPath Dependency Cycle' not in str(msg):
            message = ' '.join(message_lines[0].split(':')[1:])
        else:
            message = '\n'.join(message_lines)

        return message


class BindNotFound(XFormException):
    pass


class SuiteError(AppManagerException):
    pass


class MediaResourceError(SuiteError):
    pass


class ResourceOverrideError(SuiteError):
    pass


class ParentModuleReferenceError(SuiteError):
    pass


class SuiteValidationError(SuiteError):
    pass


class LocationXPathValidationError(AppManagerException):
    pass


class UnknownInstanceError(SuiteError):
    pass


class DuplicateInstanceIdError(SuiteError):
    pass


class ConfigurableReportException(AppManagerException):
    pass


class NoMatchingFilterException(ConfigurableReportException):
    pass


class XPathValidationError(SuiteValidationError):

    def __init__(self, *args, **kwargs):
        self.module = kwargs.pop('module', None)
        self.form = kwargs.pop('form', None)
        super(XPathValidationError, self).__init__(*args, **kwargs)


class CaseXPathValidationError(XPathValidationError):
    pass


class UsercaseXPathValidationError(XPathValidationError):
    pass


class PracticeUserException(AppManagerException):
    """ For errors related to misconfiguration of app.practice_mobile_worker_id """
    def __init__(self, *args, **kwargs):
        self.build_profile_id = kwargs.pop('build_profile_id', None)
        super(PracticeUserException, self).__init__(*args, **kwargs)


class AppLinkError(AppManagerException):
    pass


class CaseSearchConfigError(AppManagerException):
    pass


class SavedAppBuildException(AppManagerException):
    pass


class MultimediaMissingError(AppManagerException):
    pass


class BuildNotFoundException(AppManagerException):
    pass


class BuildConflictException(Exception):
    pass


class AppValidationError(AppManagerException):
    def __init__(self, errors):
        self.errors = errors


class DangerousXmlException(Exception):
    pass


class AppMisconfigurationError(AppManagerException):
    """Errors in app configuration that are the user's responsibility"""


class CannotRestoreException(Exception):
    """Errors that inherit from this exception will always fail hard in restores"""


class MobileUCRTooLargeException(CannotRestoreException):

    def __init__(self, message, row_count):
        super().__init__(message)
        self.row_count = row_count


class AppInDifferentDomainException(AppManagerException):
    """
    We generally request an app with a domain and an app_id.
    If the returned app is not in the targeted domain, we raise this exception.
    """
    pass


class InvalidPropertyException(Exception):
    def __init__(self, invalid_property):
        self.invalid_property = invalid_property
        message = f"Invalid key found: {self.invalid_property}"
        super().__init__(message)


class MissingPropertyException(Exception):
    def __init__(self, *missing_properties):
        self.missing_properties = missing_properties
        if self.missing_properties:
            message = f"The following properties were not found: {', '.join(self.missing_properties)}"
        else:
            message = "No missing properties specified"
        super().__init__(message)


class DiffConflictException(Exception):
    def __init__(self, *conflicting_keys):
        self.conflicting_keys = conflicting_keys
        if self.conflicting_keys:
            message = f"The following keys were affected by multiple actions: {', '.join(self.conflicting_keys)}"
        else:
            message = "No conflicting keys specified"
        super().__init__(message)
