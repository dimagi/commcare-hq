from django.core.urlresolvers import reverse, NoReverseMatch
from corehq.apps.reports.standard.deployments import DeploymentsReport
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.standard.forms.filters import SubmissionTypeFilter, SubmissionErrorType
from corehq.apps.reports.analytics.esaccessors import get_paged_forms_by_type
from corehq.const import SERVER_DATETIME_FORMAT
from corehq.util.timezones.conversions import ServerTime

from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.parsing import string_to_utc_datetime
from corehq.apps.reports.display import xmlns_to_name
from django.utils.translation import ugettext_noop, ugettext as _


def _compare_submissions(x, y):
    # these are backwards because we want most recent to come first
    return cmp(y.received_on, x.received_on)


class SubmissionErrorReport(DeploymentsReport):
    name = ugettext_noop("Raw Forms, Errors & Duplicates")
    slug = "submit_errors"
    ajax_pagination = True
    asynchronous = False

    fields = ['corehq.apps.reports.standard.forms.filters.SubmissionTypeFilter']

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

    @property
    @memoized
    def paged_result(self):
        doc_types = map(
            lambda filter_: filter_.doc_type,
            filter(lambda filter_: filter_.show, self.submitfilter)
        )
        return get_paged_forms_by_type(
            self.domain,
            doc_types,
            start=self.pagination.start,
            size=self.pagination.count,
        )

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
        return self.paged_result.total

    @property
    def rows(self):
        EMPTY_ERROR = _("No Error")
        EMPTY_USER = _("No User")
        EMPTY_FORM = _("Unknown Form")

        def _to_row(xform_dict):
            def _fmt_url(doc_id):
                if xform_dict['doc_type'] in [
                        "XFormInstance",
                        "XFormArchived",
                        "XFormError",
                        "XFormDeprecated"]:
                    view_name = 'render_form_data'
                else:
                    view_name = 'download_form'
                try:
                    return "<a class='ajax_dialog' href='%(url)s'>%(text)s</a>" % {
                        "url": reverse(view_name, args=[self.domain, doc_id]),
                        "text": _("View Form")
                    }
                except NoReverseMatch:
                    return 'unable to view form'

            def _fmt_date(somedate):
                time = ServerTime(somedate).user_time(self.timezone).done()
                return time.strftime(SERVER_DATETIME_FORMAT)

            if xform_dict['form'].get('meta'):
                form_name = xmlns_to_name(
                    self.domain,
                    xform_dict.get('xmlns'),
                    app_id=xform_dict.get('app_id'),
                )
                form_username = xform_dict['form']['meta'].get('username', EMPTY_USER)
            else:
                form_name = EMPTY_FORM
                form_username = EMPTY_USER
            return [
                _fmt_url(xform_dict['_id']),
                form_username,
                _fmt_date(string_to_utc_datetime(xform_dict['received_on'])),
                form_name,
                SubmissionErrorType.display_name_by_doc_type(xform_dict['doc_type']),
                xform_dict.get('problem', EMPTY_ERROR),
            ]

        return [_to_row(xform_dict) for xform_dict in self.paged_result.hits]
