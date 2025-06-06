from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop
from django.views import View

from memoized import memoized

from dimagi.utils.parsing import string_to_utc_datetime
from django.utils.translation import gettext_lazy
from dimagi.utils.web import json_response

from corehq import toggles
from corehq.apps.reports.analytics.esaccessors import get_paged_forms_by_type, PagedResult
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.display import xmlns_to_name
from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter as EMWF
from corehq.apps.reports.filters.forms import FormsByApplicationFilter
from corehq.apps.reports.standard.deployments import DeploymentsReport
from corehq.apps.reports.standard.monitoring import MultiFormDrilldownMixin
from corehq.apps.reports.standard.forms.filters import SubmissionTypeFilter
from corehq.apps.users.util import cached_user_id_to_username
from corehq.const import SERVER_DATETIME_FORMAT
from corehq.form_processor.reprocess import ReprocessingError
from corehq.util import cmp
from corehq.util.timezones.conversions import ServerTime


def _compare_submissions(x, y):
    # these are backwards because we want most recent to come first
    return cmp(y.received_on, x.received_on)


class SubmissionErrorReport(DeploymentsReport, MultiFormDrilldownMixin):
    name = gettext_noop("Raw Forms, Errors & Duplicates")
    description = gettext_lazy("View all submissions, including errors and archived forms.")
    slug = "submit_errors"
    ajax_pagination = True
    asynchronous = False
    base_template = 'reports/standard/bootstrap3/submission_error_report.html'

    fields = ['corehq.apps.reports.filters.users.ExpandedMobileWorkerFilter',
              'corehq.apps.reports.standard.forms.filters.SubmissionTypeFilter',
              'corehq.apps.reports.filters.forms.FormsByApplicationFilter']

    @property
    @memoized
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn(_("View Form"), sortable=False),
                                   DataTablesColumn(_("Username"), prop_name="form.meta.username"),
                                   DataTablesColumn(_("Submit Time"), prop_name="received_on"),
                                   DataTablesColumn(_("Form Type"), sortable=False),
                                   DataTablesColumn(_("Error Type"), sortable=False),
                                   DataTablesColumn(_("Error Message"), sortable=False),
                                   DataTablesColumn(_("View Cases"), sortable=False))
        if self.support_toggle_enabled:
            headers.add_column(DataTablesColumn(_("Re-process Form")))
        headers.custom_sort = [[2, "desc"]]
        return headers

    _submitfilter = None

    @property
    @memoized
    def selected_user_ids(self):
        return EMWF.user_es_query(
            self.domain,
            self.get_request_param(EMWF.slug, as_list=True),
            self.request.couch_user,
        ).get_ids()

    @property
    def has_user_filters(self):
        mobile_user_and_group_slugs = self.get_request_param(EMWF.slug, as_list=True)
        return len(mobile_user_and_group_slugs) > 0

    @property
    def submitfilter(self):
        if self._submitfilter is None:
            self._submitfilter = SubmissionTypeFilter.get_filter_toggle(self.request)
        return self._submitfilter

    @property
    def form_filter_params(self):
        form_filter = FormsByApplicationFilter(self.request, self.domain)
        params = []
        for label in form_filter.rendered_labels:
            param_name = f'{form_filter.slug}_{label[2]}'
            params.append(dict(
                name=param_name,
                value=self.get_request_param(param_name, None)
            ))
        return params

    def _get_app_ids_and_xmlns(self, forms):
        app_ids = []
        xmlns_list = []
        for form in forms:
            if form['is_fuzzy']:
                continue
            if form['app_id']:
                app_ids.append(form['app_id'])
            if form['xmlns']:
                xmlns_list.append(form['xmlns'])
        return app_ids, xmlns_list

    @property
    def sort_params(self):
        sort_col_idx = int(self.request.GET['iSortCol_0'])
        col = self.headers.header[sort_col_idx]
        sort_prop = hasattr(col, "prop_name") and col.prop_name
        desc = self.request.GET.get('sSortDir_0') == 'desc'
        return sort_prop, desc

    @property
    @memoized
    def paged_result(self):
        doc_types = [filter_.doc_type for filter_ in [filter_ for filter_ in self.submitfilter if filter_.show]]
        sort_col, desc = self.sort_params
        user_ids = []
        if self.has_user_filters:
            user_ids = self.selected_user_ids
            if not user_ids:
                # We have valid user filters but no results
                return PagedResult(total=0, hits=[])
        app_ids, xmlns_list = self._get_app_ids_and_xmlns(list(self.all_relevant_forms.values()))
        return get_paged_forms_by_type(
            self.domain,
            doc_types,
            sort_col=sort_col,
            desc=desc,
            start=self.pagination.start,
            size=self.pagination.count,
            user_ids=user_ids,
            app_ids=app_ids,
            xmlns=xmlns_list,
        )

    @property
    def shared_pagination_GET_params(self):
        shared_params = super(SubmissionErrorReport, self).shared_pagination_GET_params
        shared_params.append(dict(
            name=SubmissionTypeFilter.slug,
            value=[f.type for f in self.submitfilter if f.show]
        ))
        shared_params.append(dict(
            name=EMWF.slug,
            value=EMWF.get_value(self.request, self.domain),
        ))
        if FormsByApplicationFilter.has_selections(self.request):
            shared_params.extend(self.form_filter_params)
        return shared_params

    @property
    def total_records(self):
        return self.paged_result.total

    @property
    def support_toggle_enabled(self):
        return toggles.SUPPORT.enabled_for_request(self.request)

    def _make_reproces_button(self, xform_dict):
        if not xform_dict['doc_type'] == 'XFormError':
            return ''
        return '''
        <button
            class="btn btn-default reprocess-error"
            data-form-id={}>
            Re-process Form
        </button>
        '''.format(xform_dict['_id'])

    @property
    def rows(self):
        EMPTY_ERROR = _("No Error")
        EMPTY_USER = _("No User")
        EMPTY_FORM = _("Unknown Form")

        def _to_row(xform_dict):
            def _get_url(doc_type, doc_id):
                if doc_type in [
                    "XFormInstance",
                    "XFormArchived",
                    "XFormError",
                    "XFormDeprecated",
                ]:
                    view_name = "render_form_data"
                else:
                    view_name = "download_form"
                return reverse(view_name, args=[self.domain, doc_id])

            def _fmt_url(url, link_text):
                return format_html(
                    "<a class='ajax_dialog' href='{url}'>{text}</a>",
                    url=url,
                    text=link_text,
                )

            def _fmt_date(somedate):
                time = ServerTime(somedate).user_time(self.timezone).done()
                return time.strftime(SERVER_DATETIME_FORMAT)

            if xform_dict['form'].get('meta'):
                form_name = xmlns_to_name(
                    self.domain,
                    xform_dict.get('xmlns'),
                    app_id=xform_dict.get('app_id'),
                    form_name=xform_dict['form'].get('@name'),
                )
                form_username = xform_dict['form']['meta'].get('username', EMPTY_USER)
            else:
                form_name = EMPTY_FORM
                form_username = EMPTY_USER

            error_type = SubmissionTypeFilter.display_name_by_doc_type(xform_dict['doc_type'])
            if xform_dict['doc_type'] == "XFormArchived":
                archive_operations = [operation for operation in xform_dict.get('history')
                                      if operation.get('operation') == 'archive']
                if archive_operations:
                    error_type = _("{username} {archived_form} on {date}").format(
                        username=cached_user_id_to_username(archive_operations[-1].get('user')) or "",
                        archived_form=SubmissionTypeFilter.display_name_by_doc_type(xform_dict['doc_type']),
                        date=_fmt_date(string_to_utc_datetime(archive_operations[-1].get('date'))),
                    )

            try:
                url = _get_url(xform_dict['doc_type'], xform_dict['_id'])
            except NoReverseMatch:
                view_form_link = _("Unable to view form")
                view_case_link = _("Unable to view case")
            else:
                view_form_link = _fmt_url(url, _("View Form"))
                view_case_link = _fmt_url(f'{url}#form-case-data', _("View Cases"))
            return [
                view_form_link,
                form_username,
                _fmt_date(string_to_utc_datetime(xform_dict['received_on'])),
                form_name,
                error_type,
                xform_dict.get('problem', EMPTY_ERROR),
                view_case_link,
                self._make_reproces_button(xform_dict) if self.support_toggle_enabled else '',
            ]

        return [_to_row(xform_dict) for xform_dict in self.paged_result.hits]


class ReprocessXFormErrorView(View):
    urlname = 'reprocess_xform_errors'
    http_method_names = ['post']

    def post(self, request, domain):
        from corehq.form_processor.reprocess import reprocess_xform_error_by_id

        form_id = request.POST['form_id']
        if not form_id:
            return json_response({
                'success': False,
                'failure_reason': 'Missing "form_id"'
            })

        try:
            reprocess_xform_error_by_id(form_id, domain=domain)
        except ReprocessingError as e:
            return json_response({
                'success': False,
                'failure_reason': str(e),
            })
        else:
            return json_response({
                'success': True,
            })
