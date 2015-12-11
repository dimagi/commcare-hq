import couchdbkit


class AppManagerException(Exception):
    pass


class VersioningError(AppManagerException):
    """For errors that violate the principles of versioning in VersionedDoc"""
    pass


class ModuleNotFoundException(AppManagerException, IndexError):
    pass


class FormNotFoundException(AppManagerException, IndexError):
    pass


class IncompatibleFormTypeException(AppManagerException):
    pass


class AppEditingError(AppManagerException):
    pass


class ModuleIdMissingException(AppManagerException):
    pass


class RearrangeError(AppEditingError):
    pass


class ConflictingCaseTypeError(AppEditingError):
    pass


class XFormException(AppManagerException):
    pass


class BlankXFormError(XFormException):
    pass


class CaseError(XFormException):
    pass


class ScheduleError(XFormException):
    pass


class XFormValidationError(XFormException):
    def __init__(self, fatal_error, version="1.0", validation_problems=None):
        self.fatal_error = fatal_error
        self.version = version
        self.validation_problems = validation_problems

    def __str__(self):
        fatal_error_text = self.format_v1(self.fatal_error)
        ret = u"Validation Error%s" % (': %s' % fatal_error_text if fatal_error_text else '')
        problems = filter(lambda problem: problem['message'] != self.fatal_error, self.validation_problems)
        if problems:
            ret += u"\n\nMore information:"
            for problem in problems:
                ret += u"\n{type}: {msg}".format(type=problem['type'].title(), msg=problem['message'])
        return ret

    def format_v1(self, msg):
        if self.version != '1.0':
            return msg
        # Don't display the first two lines which say "Parsing form..." and 'Title: "{form_name}"'
        #
        # ... and if possible split the third line that looks like e.g. "org.javarosa.xform.parse.XFormParseException: Select question has no choices"
        # and just return the undecorated string
        #
        # ... unless the first line says
        message_lines = unicode(msg).split('\n')[2:]
        if len(message_lines) > 0 and ':' in message_lines[0] and 'XPath Dependency Cycle' not in unicode(msg):
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


class ParentModuleReferenceError(SuiteError):
    pass


class SuiteValidationError(SuiteError):
    pass


class XFormIdNotUnique(AppManagerException, couchdbkit.MultipleResultsFound):
    pass


class LocationXpathValidationError(AppManagerException):
    pass


class UnknownInstanceError(SuiteError):
    pass


class ConfigurableReportException(AppManagerException):
    pass


class NoMatchingFilterException(ConfigurableReportException):
    pass


class CaseXPathValidationError(SuiteValidationError):
    pass
