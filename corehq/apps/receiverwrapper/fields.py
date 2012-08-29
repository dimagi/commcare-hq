from corehq.apps.reports.models import HQToggle
from corehq.apps.reports.fields import ReportField

class SubmitToggle(HQToggle):
    
    def __init__(self,  type, show, name, doc_type):
        super(SubmitToggle, self).__init__(type, show, name)
        self.doc_type = doc_type

class SubmissionErrorType(object):
    # This is largely modeled off how the user filter works
    SUCCESS = 0
    PARTIAL_SUCCESS = 1
    DUPLICATE = 2
    OVERWRITTEN = 3
    UNKNOWN_ERROR = 4
    
    doc_types = ["XFormInstance", "XFormError", "XFormDuplicate", "XFormDeprecated", "SubmissionErrorLog"]
    human_readable = ["Normal Form", "Form with Errors", "Duplicate Form", "Overwritten Form", "Generic Error"]
    
    error_defaults = [False, True, False, False, True]
    success_defaults = [True, False, False, False, False]

    @classmethod
    def display_name_by_doc_type(cls, doc_type):
        return cls.display_name_by_index(cls.doc_types.index(doc_type))
    
    @classmethod
    def display_name_by_index(cls, index):
        return cls.human_readable[index]
    
    @classmethod
    def doc_type_by_index(cls, index):
        return cls.doc_types[index]
    
    @classmethod
    def use_error_defaults(cls):
        return [SubmitToggle(i, cls.error_defaults[i], name, cls.doc_types[i]) for i, name in enumerate(cls.human_readable)]

    @classmethod
    def use_success_defaults(cls):
        return [SubmitToggle(i, cls.success_defaults[i], name, cls.doc_types[i]) for i, name in enumerate(cls.human_readable)]

    @classmethod
    def use_filter(cls, filter):
        return [SubmitToggle(i, unicode(i) in filter, name, cls.doc_types[i]) for i, name in enumerate(cls.human_readable)]

class SubmissionTypeField(ReportField):
    slug = "submitfilter"
    template = "reports/fields/submit_error_types.html"

    def update_context(self):
        self.context['submission_types'] = self.get_filter_toggle(self.request)

    @classmethod
    def get_filter_toggle(cls, request):
        filter = None
        try:
            if request.GET.get(cls.slug, ''):
                filter = request.GET.getlist(cls.slug)
        except KeyError:
            pass
        
        if filter:
            return SubmissionErrorType.use_filter(filter)
        else:
            return SubmissionErrorType.use_error_defaults()
        