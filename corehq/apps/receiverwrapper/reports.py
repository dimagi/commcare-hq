from django.core.urlresolvers import reverse, NoReverseMatch
import pytz
from corehq.apps.reports.standard.deployments import DeploymentsReport
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.util.timezones import utils as tz_utils
from corehq.util.timezones.conversions import ServerTime
from couchforms.models import XFormError
from corehq.apps.receiverwrapper.filters import SubmissionErrorType, \
    SubmissionTypeFilter
from dimagi.utils.couch.pagination import FilteredPaginator, CouchFilter
from corehq.apps.reports.display import xmlns_to_name
from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _

def compare_submissions(x, y):
    # these are backwards because we want most recent to come first
    return cmp(y.received_on, x.received_on)

class SubmitFilter(CouchFilter):
    
    def __init__(self, domain, doc_type):
        self.domain = domain
        self.doc_type = doc_type
        self._kwargs = { "endkey":       [self.domain, "by_type", self.doc_type],
                         "startkey":     [self.domain, "by_type", self.doc_type, {}],
                         "reduce":       False,
                         "descending":   True }
        
    
    def get_total(self):
        return XFormError.view("couchforms/all_submissions_by_domain",
                               **self._kwargs).count()

    def get(self, count):
        # this is a hack, but override the doc type because there is an
        # equivalent doc type in the view
        def _update_doc_type(form):
            form.doc_type = self.doc_type
            return form 
        return [_update_doc_type(form) for form in \
                 XFormError.view("couchforms/all_submissions_by_domain",
                                 include_docs=True,
                                 limit=count,
                                 **self._kwargs)]


class SubmissionErrorReport(DeploymentsReport):
    name = ugettext_noop("Raw Forms, Errors & Duplicates")
    slug = "submit_errors"
    ajax_pagination = True
    asynchronous = False

    fields = ['corehq.apps.receiverwrapper.filters.SubmissionTypeFilter',
              ]

    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn(_("View Form")),
                                   DataTablesColumn(_("Username")),
                                   DataTablesColumn(_("Submit Time")),
                                   DataTablesColumn(_("Form Type")),
                                   DataTablesColumn(_("Error Type")),
                                   DataTablesColumn(_("Error Message")))
        headers.no_sort = True
        return headers

    _submitfilter = None
    @property
    def submitfilter(self):
        if self._submitfilter is None:
            self._submitfilter = SubmissionTypeFilter.get_filter_toggle(self.request)
        return self._submitfilter

    _paginator_results = None
    @property
    def paginator_results(self):
        if self._paginator_results is None:
            filters = [SubmitFilter(self.domain, toggle.doc_type) for toggle in self.submitfilter if toggle.show]
            self._paginator_results = FilteredPaginator(filters, compare_submissions)
        return self._paginator_results

    @property
    def shared_pagination_GET_params(self):
        shared_params = super(SubmissionErrorReport, self).shared_pagination_GET_params
        shared_params.append(dict(
            name=SubmissionTypeFilter.slug,
            value=[f.type for f in self.submitfilter if f.show]
        ))
        return shared_params

    @property
    def total_records(self):
        return XFormError.view("couchforms/all_submissions_by_domain",
            startkey=[self.domain, "by_type"],
            endkey=[self.domain, "by_type", {}],
            reduce=False).count()

    @property
    def total_filtered_records(self):
        return self.paginator_results.total

    @property
    def rows(self):
        EMPTY_ERROR = _("No Error")
        EMPTY_USER = _("No User")
        EMPTY_FORM = _("Unknown Form")

        items = self.paginator_results.get(self.pagination.start, self.pagination.count)
        
        def _to_row(error_doc):
            def _fmt_url(doc_id):
                view_name = 'render_form_data' \
                    if error_doc.doc_type in ["XFormInstance", "XFormArchived", "XFormError"] \
                    else 'download_form'
                try:
                    return "<a class='ajax_dialog' href='%(url)s'>%(text)s</a>" % {
                        "url": reverse(view_name, args=[self.domain, doc_id]),
                        "text": _("View Form")
                    }
                except NoReverseMatch:
                    return 'unable to view form'
            
            def _fmt_date(somedate):
                time = ServerTime(somedate).user_time(self.timezone).done()
                return time.strftime("%Y-%m-%d %H:%M:%S")
            
            return [_fmt_url(error_doc.get_id),
                    error_doc.metadata.username if error_doc.metadata else EMPTY_USER,
                    _fmt_date(error_doc.received_on),
                    xmlns_to_name(self.domain, error_doc.xmlns, app_id=getattr(error_doc, 'app_id', None)) if error_doc.metadata else EMPTY_FORM,
                    SubmissionErrorType.display_name_by_doc_type(error_doc.doc_type),
                    error_doc.problem or EMPTY_ERROR]
        
        return [_to_row(error_doc) for error_doc in items]
