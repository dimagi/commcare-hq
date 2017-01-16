from django.contrib.humanize.templatetags.humanize import naturaltime
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _, ugettext_lazy, ugettext_noop

from dimagi.utils.decorators.memoized import memoized

from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.es import cases as case_es
from corehq.apps.groups.models import Group
from corehq.apps.reports.display import FormDisplay
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericReportView
from corehq.apps.reports.models import HQUserType
from corehq.apps.reports.standard import ProjectReport
from corehq.apps.reports.standard.cases.basic import CaseListMixin
from corehq.apps.reports.standard.cases.data_sources import CaseDisplay
from corehq.apps.reports.standard.inspect import SubmitHistoryMixin
from corehq.apps.reports.filters.base import BaseSingleOptionFilter

from .dispatcher import EditDataInterfaceDispatcher


class DataInterface(GenericReportView):
    # overriding properties from GenericReportView
    section_name = ugettext_noop("Data")
    base_template = "reports/standard/base_template.html"
    asynchronous = True
    dispatcher = EditDataInterfaceDispatcher
    exportable = False

    @property
    def default_report_url(self):
        return reverse('data_interfaces_default', args=[self.request.project])


class CaseReassignmentInterface(CaseListMixin, DataInterface):
    name = ugettext_noop("Reassign Cases")
    slug = "reassign_cases"
    report_template_path = 'data_interfaces/interfaces/case_management.html'

    @property
    @memoized
    def es_results(self):
        query = self._build_query()
        # FB 183468: Don't allow user cases to be reassigned
        query = query.NOT(case_es.case_type(USERCASE_TYPE))
        return query.run().raw

    @property
    @memoized
    def all_case_sharing_groups(self):
        return Group.get_case_sharing_groups(self.domain)

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(mark_safe(
                'Select  <a href="#" class="select-all btn btn-xs btn-info">all'
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
        checkbox = mark_safe('<input type="checkbox" class="selected-commcare-case" data-caseid="%(case_id)s" data-owner="%(owner)s" data-ownertype="%(owner_type)s" />')
        for row in self.es_results['hits'].get('hits', []):
            case = self.get_case(row)
            display = CaseDisplay(self, case)
            yield [
                checkbox % dict(case_id=case['_id'], owner=display.owner_id, owner_type=display.owner_type),
                display.case_link,
                display.case_type,
                display.owner_display,
                naturaltime(display.parse_date(display.case['modified_on'])),
            ]

    @property
    def report_context(self):
        context = super(CaseReassignmentInterface, self).report_context
        active_users = self.get_all_users_by_domain(user_filter=tuple(HQUserType.all()), simplified=True)
        context.update(
            users=[dict(ownerid=user.user_id, name=user.username_in_report, type="user")
                   for user in active_users],
            groups=[dict(ownerid=group.get_id, name=group.name, type="group")
                    for group in self.all_case_sharing_groups],
        )
        return context


class FormManagementMode(object):
    """
        Simple container for bulk form archive/restore mode and messages
    """
    ARCHIVE_MODE = "archive"
    RESTORE_MODE = "restore"

    filter_options = [(ARCHIVE_MODE, ugettext_lazy('Normal Forms')),
                      (RESTORE_MODE, ugettext_lazy('Archived Forms'))]

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
    label = ugettext_lazy('Archived/Restored')
    help_text = mark_safe("Archived forms are removed from reports and exports and "
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


class BulkFormManagementInterface(SubmitHistoryMixin, DataInterface, ProjectReport):
    name = ugettext_noop("Manage Forms")
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
                mark_safe(
                    """
                    Select  <a class="select-visible btn btn-xs btn-info">all</a>
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
        for form in self.es_query_result.hits:
            display = FormDisplay(form, self)
            checkbox = mark_safe(
                """<input type="checkbox" class="xform-checkbox"
                value="{form_id}" name="xform_ids"/>"""
            )
            yield [
                checkbox.format(form_id=form["_id"]),
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
