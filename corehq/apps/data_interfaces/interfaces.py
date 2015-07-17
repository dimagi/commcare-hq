from django.contrib.humanize.templatetags.humanize import naturaltime
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop

from couchdbkit.exceptions import ResourceNotFound
from dimagi.utils.couch import get_cached_property, IncompatibleDocument, safe_index
from dimagi.utils.decorators.memoized import memoized

from corehq.apps.groups.models import Group
from corehq.apps.reports import util
from corehq.apps.reports.display import xmlns_to_name
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType
from corehq.apps.reports.generic import GenericReportView
from corehq.apps.reports.models import HQUserType
from corehq.apps.reports.standard import ProjectReport
from corehq.apps.reports.standard.cases.basic import CaseListMixin
from corehq.apps.reports.standard.cases.data_sources import CaseDisplay
from corehq.apps.reports.standard.inspect import SubmitHistoryMixin
from corehq.apps.reports.filters.base import (
    BaseReportFilter, BaseSingleOptionFilter
)
from corehq.apps.users.models import CouchUser
from corehq.const import USER_DATETIME_FORMAT_WITH_SEC
from corehq.elastic import ADD_TO_ES_FILTER
from corehq.util.dates import iso_string_to_datetime
from corehq.util.timezones.conversions import ServerTime, PhoneTime
from corehq.util.view_utils import absolute_reverse


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
    def all_case_sharing_groups(self):
        return Group.get_case_sharing_groups(self.domain)

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(mark_safe('Select  <a href="#" class="select-all btn btn-mini btn-inverse">all</a> <a href="#" class="select-none btn btn-mini btn-warning">none</a>'), sortable=False, span=2),
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
            user_ids=self.user_ids,
        )
        return context


class FormManagementMode(object):
    ARCHIVE_MODE = "archive"
    RESTORE_MODE = "restore"

    filter_options = [(ARCHIVE_MODE, _('Normal Forms')), (RESTORE_MODE, _('Archived Forms'))]

    def __init__(self, mode, validate=False):
        if mode == self.RESTORE_MODE:
            self.mode_name = self.RESTORE_MODE
            self.xform_filter = ADD_TO_ES_FILTER['archived_forms']
            self.button_text = "Restore selected Forms"
            self.button_class = "btn-primary"
            self.status_page_title = "Restore Forms Status"
            self.progress_text = "Restoring your forms, this may take some time..."
            self.complete_short = "Restore complete!"
            self.complete_long = "Your forms are succesfully restored"
            self.success_text = "Succesfully restored "
            self.fail_text = "Restore Failed. Details:"
            self.error_text = "Problem restoring your forms! Please try again or report an issue"
        else:
            self.mode_name = self.ARCHIVE_MODE
            self.xform_filter = ADD_TO_ES_FILTER['forms']
            self.button_text = "Archive selected forms"
            self.button_class = "btn-danger"
            self.status_page_title = "Archive Forms Status"
            self.progress_text = "Archiving your forms, this may take some time..."
            self.complete_short = "Archive complete!"
            self.complete_long = "Your forms are succesfully archived"
            self.success_text = "Succesfully archived "
            self.fail_text = "Archive Failed. Details:"
            self.error_text = "Problem archiving your forms! Please try again or report an issue"
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
    # ToDo. Move to a better place
    slug = 'archive_or_restore'
    default_text = ugettext_noop("Select...")
    placeholder = ''
    label = _('Archived/Restored')

    @property
    def options(self):
        return FormManagementMode.filter_options

    @property
    def selected(self):
        return FormManagementMode(self.request.GET.get(self.slug)).mode_name


class BulkArchiveFormInterface(SubmitHistoryMixin, DataInterface, ProjectReport):
    name = ugettext_noop("Manage Forms")
    slug = "bulk_archive_forms"

    report_template_path = 'data_interfaces/interfaces/archive_forms.html'

    def __init__(self, request, **kwargs):
        super(BulkArchiveFormInterface, self).__init__(request, **kwargs)
        self.fields = self.fields + ['corehq.apps.data_interfaces.interfaces.ArchiveOrNormalFormFilter']
        self.mode = FormManagementMode(request.GET.get('archive_or_restore'))

    @property
    def template_context(self):
        context = super(BulkArchiveFormInterface, self).template_context
        import json
        context.update(filters_as_es_query=json.dumps(self.filters_as_es_query()))
        context.update({
            "mode": self.mode,
            "total_xForms": int(self.es_results['hits']['total']),
        })
        return context

    def _es_xform_filter(self):
        return self.mode.xform_filter

    @property
    def headers(self):
        h = [
            DataTablesColumn(mark_safe('Select  <a class="select-all btn btn-mini btn-inverse">all</a> <a class="select-none btn btn-mini btn-warning">none</a>'), sortable=False, span=2),
            DataTablesColumn(_("View Form")),
            DataTablesColumn(_("Username"), prop_name='form.meta.username'),
            DataTablesColumn(
                _("Submission Time") if self.by_submission_time
                else _("Completion Time"),
                prop_name=self.time_field
            ),
            DataTablesColumn(_("Form"), prop_name='form.@name'),
        ]
        h.extend([DataTablesColumn(field) for field in self.other_fields])
        return DataTablesHeader(*h)

    @property
    def rows(self):
        # ToDo - refactor following into FormDisplay to use in SubmitHistoryMixin and here
        def form_data_link(instance_id):
            return "<a class='ajax_dialog' target='_new' href='%(url)s'>%(text)s</a>" % {
                "url": absolute_reverse('render_form_data', args=[self.domain, instance_id]),
                "text": _("View Form")
            }

        submissions = [res['_source'] for res in self.es_results.get('hits', {}).get('hits', [])]

        for form in submissions:
            uid = form["form"]["meta"]["userID"]
            username = form["form"]["meta"].get("username")
            try:
                if username not in ['demo_user', 'admin']:
                    full_name = get_cached_property(CouchUser, uid, 'full_name', expiry=7*24*60*60)
                    name = '"%s"' % full_name if full_name else ""
                else:
                    name = ""
            except (ResourceNotFound, IncompatibleDocument):
                name = "<b>[unregistered]</b>"

            time = iso_string_to_datetime(safe_index(form, self.time_field.split('.')))
            if self.by_submission_time:
                user_time = ServerTime(time).user_time(self.timezone)
            else:
                user_time = PhoneTime(time, self.timezone).user_time(self.timezone)

            checkbox = mark_safe(
                """<input type="checkbox" class="xform-checkbox"
                value="{form_id}" name="xform_ids"/>""")

            init_cells = [
                checkbox.format(form_id=form["_id"]),
                form_data_link(form["_id"]),
                (username or _('No data for username')) + (" %s" % name if name else ""),
                user_time.ui_string(USER_DATETIME_FORMAT_WITH_SEC),
                xmlns_to_name(self.domain, form.get("xmlns"), app_id=form.get("app_id")),
            ]

            def cell(field):
                return form["form"].get(field)
            init_cells.extend([cell(field) for field in self.other_fields])
            yield init_cells
