from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.reports.filters.base import BaseReportFilter
from corehq.apps.reports.models import HQToggle
from django.utils.translation import ugettext_lazy
import six


class SubmitToggle(HQToggle):
    
    def __init__(self,  type, show, name, doc_type):
        super(SubmitToggle, self).__init__(type, show, name)
        self.doc_type = doc_type


class SubmissionTypeFilter(BaseReportFilter):
    slug = "submitfilter"
    label = ugettext_lazy("Submission Type")
    template = "reports/filters/submit_error_types.html"

    doc_types = ["XFormInstance", "XFormError", "XFormDuplicate", "XFormDeprecated", "SubmissionErrorLog",
                 "XFormArchived"]

    human_readable = [ugettext_lazy("Normal Form"),
                      ugettext_lazy("Form with Errors"),
                      ugettext_lazy("Duplicate Form"),
                      ugettext_lazy("Overwritten Form"),
                      ugettext_lazy("Generic Error"),
                      ugettext_lazy("Archived Form")]

    @property
    def filter_context(self):
        return {
            'submission_types': self.get_filter_toggle(self.request)
        }

    @classmethod
    def get_filter_toggle(cls, request):
        filter_ = request.GET.getlist(cls.slug, None)
        return cls.use_filter(filter_)

    @classmethod
    def use_filter(cls, filter):
        return [SubmitToggle(i, six.text_type(i) in filter, name, cls.doc_types[i]) for i, name in
                enumerate(cls.human_readable)]

    @classmethod
    def display_name_by_doc_type(cls, doc_type):
        return cls.human_readable[cls.doc_types.index(doc_type)]
