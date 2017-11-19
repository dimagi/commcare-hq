from __future__ import absolute_import
from corehq.apps.reports.filters.base import BaseReportFilter
from corehq.apps.reports.models import HQToggle
from django.utils.translation import ugettext_lazy
import six


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
    ARCHIVED = 5
    
    doc_types = ["XFormInstance", "XFormError", "XFormDuplicate", "XFormDeprecated", "SubmissionErrorLog", "XFormArchived"]
    human_readable = [ugettext_lazy("Normal Form"),
                      ugettext_lazy("Form with Errors"),
                      ugettext_lazy("Duplicate Form"),
                      ugettext_lazy("Overwritten Form"),
                      ugettext_lazy("Generic Error"),
                      ugettext_lazy("Archived Form")]
    
    error_defaults = [False, True, False, False, True, False]
    success_defaults = [True, False, False, False, False, False]

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
        return [SubmitToggle(i, six.text_type(i) in filter, name, cls.doc_types[i]) for i, name in enumerate(cls.human_readable)]


class SubmissionTypeFilter(BaseReportFilter):
    # don't use this as an example / best practice
    # todo: cleanup
    slug = "submitfilter"
    label = ugettext_lazy("Submission Type")
    template = "reports/filters/submit_error_types.html"

    @property
    def filter_context(self):
        return {
            'submission_types': self.get_filter_toggle(self.request)
        }

    @classmethod
    def get_filter_toggle(cls, request):
        filter_ = request.GET.getlist(cls.slug, None)
        if filter_:
            return SubmissionErrorType.use_filter(filter_)
        else:
            return SubmissionErrorType.use_error_defaults()
