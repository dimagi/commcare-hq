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


class ArchiveOrNormalFormFilter(BaseSingleOptionFilter):
    # ToDo. Move to a better place
    slug = 'archive'
    default_text = ugettext_noop("Select...")
    placeholder = ''
    label = _('Archived Form')

    @property
    def options(self):
        return [('normal', _('Normal Forms')), ('archived', _('Archived Forms'))]

    @property
    def selected(self):
        return 'normal'


class BulkArchiveFormInterface(SubmitHistoryMixin, DataInterface, ProjectReport):
    name = ugettext_noop("Archive Forms")
    slug = "bulk_archive_forms"

    report_template_path = 'data_interfaces/interfaces/archive_forms.html'

    def __init__(self, request, **kwargs):
        super(BulkArchiveFormInterface, self).__init__(request, **kwargs)
        self.fields = self.fields + ['corehq.apps.data_interfaces.interfaces.ArchiveOrNormalFormFilter']

    @property
    def restore_mode(self):
        return True if self.request.GET.get('archive') == 'archived' else False

    def _es_xform_filter(self):
        if self.restore_mode:
            return ADD_TO_ES_FILTER['archived_forms']
        else:
            return ADD_TO_ES_FILTER['forms']

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
