from django.contrib.humanize.templatetags.humanize import naturaltime
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, gettext_noop
from memoized import memoized
from soil.util import expose_cached_download

from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.es import cases as case_es
from corehq.apps.groups.models import Group
from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.display import FormDisplay
from corehq.apps.reports.filters.base import BaseSingleOptionFilter
from corehq.apps.reports.generic import GenericReportView
from corehq.apps.reports.standard import ProjectReport
from corehq.apps.reports.standard.cases.basic import CaseListMixin
from corehq.apps.reports.standard.cases.data_sources import CaseDisplayES
from corehq.apps.reports.standard.inspect import SubmitHistoryMixin
from corehq.util.timezones.utils import parse_date
from .dispatcher import EditDataInterfaceDispatcher, BulkEditDataInterfaceDispatcher


class DataInterface(GenericReportView):
    # overriding properties from GenericReportView
    section_name = gettext_noop("Data")
    base_template = "reports/standard/base_template.html"
    asynchronous = True
    dispatcher = EditDataInterfaceDispatcher
    exportable = False

    @property
    def default_report_url(self):
        return reverse('data_interfaces_default', args=[self.request.project.name])


class BulkDataInterface(DataInterface):
    dispatcher = BulkEditDataInterfaceDispatcher


@location_safe
class CaseReassignmentInterface(CaseListMixin, BulkDataInterface):
    name = gettext_noop("Reassign Cases")
    slug = "reassign_cases"
    report_template_path = 'data_interfaces/interfaces/case_management.html'
    action = "reassign"
    action_text = gettext_lazy("Reassign")

    @property
    @memoized
    def es_results(self):
        return self._es_query.run().raw

    @property
    def _es_query(self):
        query = self._build_query()
        # FB 183468: Don't allow user cases to be reassigned
        return query.NOT(case_es.case_type(USERCASE_TYPE))

    @property
    def template_context(self):
        context = super(CaseReassignmentInterface, self).template_context
        context.update({
            "total_cases": self.total_records,
            "action": self.action,
            "action_text": self.action_text,
        })
        return context

    @property
    @memoized
    def all_case_sharing_groups(self):
        return Group.get_case_sharing_groups(self.domain)

    def accessible_case_sharing_locations(self, user):
        return Group.get_case_sharing_accessible_locations(self.domain, user)

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(mark_safe(  # nosec: no user input
                'Select  <a href="#" class="select-all btn btn-xs btn-default">all'
                '</a> <a href="#" class="select-none btn btn-xs btn-default">'
                'none</a>'), sortable=False, span=2),
            DataTablesColumn(_("Case Name"), span=3, prop_name="name.exact"),
            DataTablesColumn(_("Case Type"), span=2, prop_name="type.exact"),
            DataTablesColumn(_("Owner"), span=2, prop_name="owner_display", sortable=False),
            DataTablesColumn(_("Last Modified"), span=3, prop_name="modified_on"),
        )
        return headers

    @property
    def rows(self):
        checkbox_format = ('<input type="checkbox" class="selected-commcare-case"'
            ' data-caseid="{case_id}" data-owner="{owner}" data-ownertype="{owner_type}" />')

        for row in self.es_results['hits'].get('hits', []):
            es_case = self.get_case(row)
            display = CaseDisplayES(es_case, self.timezone, self.individual)
            yield [
                format_html(
                    checkbox_format,
                    case_id=es_case['_id'],
                    owner=display.owner_id,
                    owner_type=display.owner_type),
                display.case_link,
                display.case_type,
                display.owner_display,
                naturaltime(parse_date(es_case['modified_on'])),
            ]

    @property
    def bulk_response(self):
        if self.request.method != 'POST':
            return HttpResponseBadRequest()
        owner_id = self.request_params.get('new_owner_id', None)
        if not owner_id:
            return HttpResponseBadRequest(
                _("An owner_id needs to be specified to bulk reassign cases")
            )

        # If we use self.es_results we're limited to the pagination set on the
        # UI by the user
        es_results = self._es_query\
            .size(self.total_records)\
            .run().raw

        case_ids = [
            self.get_case(row)['_id']
            for row in es_results['hits'].get('hits', [])
        ]
        task_ref = expose_cached_download(
            payload=case_ids, expiry=60 * 60, file_extension=None
        )
        task = self.bulk_async_task().delay(
            self.domain,
            self.request.couch_user.get_id,
            owner_id,
            task_ref.download_id,
            self.request.META['HTTP_REFERER'],
            **self.additional_bulk_action_params,
        )
        task_ref.set_task(task)
        return HttpResponseRedirect(
            self.bulk_url(task_ref.download_id)
        )

    def bulk_url(self, download_id):
        from .views import BulkCaseActionSatusView
        return reverse(
            BulkCaseActionSatusView.urlname,
            args=[self.domain, download_id]
        ) + f'?action={self.action}'

    @staticmethod
    def bulk_async_task():
        from .tasks import bulk_case_reassign_async
        return bulk_case_reassign_async

    @property
    def additional_bulk_action_params(self):
        return {}


@location_safe
class CaseCopyInterface(CaseReassignmentInterface):
    name = gettext_noop("Copy Cases")
    slug = "copy_cases"
    report_template_path = 'data_interfaces/interfaces/case_management.html'
    action = "copy"
    action_text = gettext_lazy("Copy")

    @property
    @memoized
    def es_results(self):
        query = self._build_query()
        owner_id = self.request.GET.get('individual')
        if owner_id:
            query = query.owner(owner_id)

        return query.run().raw

    @property
    def template_context(self):
        context = super(CaseCopyInterface, self).template_context
        context.update({
            "action": self.action,
            "action_text": self.action_text,
        })
        return context

    @property
    def fields(self):
        return [
            'corehq.apps.reports.filters.case_list.CaseListFilter',
            'corehq.apps.reports.filters.select.MultiCaseTypeFilter',
            'corehq.apps.reports.standard.cases.filters.CaseSearchFilter',
            'corehq.apps.reports.standard.cases.filters.SensitiveCaseProperties',
        ]

    @staticmethod
    def bulk_async_task():
        from .tasks import bulk_case_copy_async
        return bulk_case_copy_async

    @property
    def additional_bulk_action_params(self):
        return {
            'sensitive_properties': self._parse_sensitive_props(self.request_params['sensitive_properties']),
        }

    @staticmethod
    def _parse_sensitive_props(props):
        return {p['name']: p['label'] for p in props if p['name']}


class FormManagementMode(object):
    """
        Simple container for bulk form archive/restore mode and messages
    """
    ARCHIVE_MODE = "archive"
    RESTORE_MODE = "restore"

    filter_options = [(ARCHIVE_MODE, gettext_lazy('Normal Forms')),
                      (RESTORE_MODE, gettext_lazy('Archived Forms'))]

    def __init__(self, mode, validate=False):
        if mode == self.RESTORE_MODE:
            self.mode_name = self.RESTORE_MODE
            self.button_text = _("Restore selected Forms")
            self.button_class = _("btn-primary")
            self.status_page_title = _("Restore Forms Status")
            self.progress_text = _("Restoring your forms, this may take some time...")
            self.complete_short = _("Restore complete!")
            self.success_text = _("Successfully restored ")
            self.fail_text = _("Restore Failed. Details:")
            self.error_text = _("Problem restoring your forms! Please try again or report an issue")
            self.help_message = _("To archive back any forms, use the Manage Forms report and "
                                  "filter to Normal forms")
        else:
            self.mode_name = self.ARCHIVE_MODE
            self.button_text = _("Archive selected forms")
            self.button_class = _("btn-danger")
            self.status_page_title = _("Archive Forms Status")
            self.progress_text = _("Archiving your forms, this may take some time...")
            self.complete_short = _("Archive complete!")
            self.success_text = _("Successfully archived ")
            self.fail_text = _("Archive Failed. Details:")
            self.error_text = _("Problem archiving your forms! Please try again or report an issue")
            self.help_message = _("To restore any archived forms, use the Manage Forms report and "
                                  "filter to Archived forms")
        if validate:
            self.validate_mode(mode)

    @classmethod
    def validate_mode(cls, mode):
        if mode not in [cls.ARCHIVE_MODE, cls.RESTORE_MODE]:
            raise Exception("mode should be archive or restore")
        return mode

    def is_archive_mode(self):
        return self.mode_name == self.ARCHIVE_MODE


class ArchiveOrNormalFormFilter(BaseSingleOptionFilter):
    slug = 'archive_or_restore'
    placeholder = ''
    default_text = None
    label = gettext_lazy('Archived/Restored')
    help_text = mark_safe(  # nosec: no user input
        "Archived forms are removed from reports and exports and "
        "any case changes they make are reversed. Archiving forms "
        "can remove accidental form submissions. Use this report "
        "to bulk archive forms or restore a set of archived forms. "
        "<a href='https://confluence.dimagi.com/display/commcarepublic/Archive+Forms'>"
        "Learn more</a>")
    help_style_bubble = True

    @property
    def options(self):
        return FormManagementMode.filter_options

    @property
    def selected(self):
        return FormManagementMode(self.request.GET.get(self.slug)).mode_name


@location_safe
class BulkFormManagementInterface(SubmitHistoryMixin, DataInterface, ProjectReport):
    name = gettext_noop("Manage Forms")
    slug = "bulk_archive_forms"
    report_template_path = 'data_interfaces/interfaces/archive_forms.html'

    def __init__(self, request, **kwargs):
        super(BulkFormManagementInterface, self).__init__(request, **kwargs)
        self.fields = self.fields + ['corehq.apps.data_interfaces.interfaces.ArchiveOrNormalFormFilter']
        self.mode = FormManagementMode(request.GET.get('archive_or_restore'))

    @property
    def template_context(self):
        context = super(BulkFormManagementInterface, self).template_context
        context.update({
            "form_query_string": self.request.GET.urlencode(),
            "mode": self.mode,
            "total_xForms": int(self.es_query_result.total),
        })
        return context

    @property
    def es_query(self):
        query = super(BulkFormManagementInterface, self).es_query
        if self.mode.mode_name == self.mode.RESTORE_MODE:
            return query.only_archived()
        else:
            return query

    @property
    def headers(self):
        h = [
            DataTablesColumn(
                mark_safe(  # nosec: no user input
                    """
                    Select  <a class="select-visible btn btn-xs btn-default">all</a>
                    <a class="select-none btn btn-xs btn-default">none</a>
                    """
                ),
                sortable=False, span=3
            ),
            DataTablesColumn(_("View Form"), span=2),
            DataTablesColumn(_("Username"), prop_name='form.meta.username', span=3),
            DataTablesColumn(
                _("Submission Time") if self.by_submission_time
                else _("Completion Time"),
                prop_name=self.time_field,
                span=3,
            ),
            DataTablesColumn(_("Form"), prop_name='form.@name'),
        ]
        return DataTablesHeader(*h)

    @property
    def rows(self):
        checkbox_format = '<input type="checkbox" class="xform-checkbox" value="{}" name="xform_ids"/>'

        for form in self.es_query_result.hits:
            display = FormDisplay(form, self)
            yield [
                format_html(checkbox_format, form["_id"]),
                display.form_data_link,
                display.username,
                display.submission_or_completion_time,
                display.readable_form_name,
            ]

    @property
    def form_ids_response(self):
        # returns a list of form_ids
        # this is called using ReportDispatcher.dispatch(render_as='form_ids', ***) in
        # the bulk_form_management_async task
        return self.es_query.get_ids()
