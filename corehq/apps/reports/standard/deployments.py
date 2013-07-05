from couchdbkit import ResourceNotFound
from corehq.apps.app_manager.models import Application
from corehq.apps.reports import util
from corehq.apps.reports.standard import ProjectReportParametersMixin, ProjectReport
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType
from corehq.apps.reports.fields import SelectApplicationField
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.util import make_form_couch_key
from couchforms.models import XFormInstance
from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _

class DeploymentsReport(GenericTabularReport, ProjectReport, ProjectReportParametersMixin):
    """
        Base class for all deployments reports
    """
   
    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return not project.commtrack_enabled

class ApplicationStatusReport(DeploymentsReport):
    name = ugettext_noop("Application Status")
    slug = "app_status"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.GroupField',
              'corehq.apps.reports.fields.SelectApplicationField']

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn(_("Username")),
            DataTablesColumn(_("Last Seen"),sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("Application [Deployed Build]")))

    @property
    def rows(self):
        rows = []
        selected_app = self.request_params.get(SelectApplicationField.slug, '')
        UNKNOWN = _("unknown")

        for user in self.users:
            last_seen = self.table_cell(-1, _("Never"))
            app_name = None

            key = make_form_couch_key(self.domain, user_id=user.get('user_id'), app_id=selected_app if selected_app else None)
            data = XFormInstance.view(
                "reports_forms/all_forms",
                startkey=key+[{}],
                endkey=key,
                include_docs=True,
                descending=True,
                reduce=False,
                limit=1,
            ).first()

            if data:
                last_seen = util.format_relative_date(data.received_on)

                if data.version != '1':
                    build_id = data.version
                else:
                    build_id = UNKNOWN

                if data.app_id:
                    try:
                        app = Application.get(data.app_id)
                        app_name = "%s [%s]" % (app.name, build_id)
                    except ResourceNotFound:
                        pass
                else:
                    try:
                        form_data = data.get_form
                        app_name = form_data['meta']['appVersion']['#text']
                    except KeyError:
                        pass
                    
                app_name = app_name or _("Unknown App")

            if app_name is None and selected_app:
                continue

            rows.append([user.get('username_in_report'), last_seen, app_name or "---"])
        return rows
