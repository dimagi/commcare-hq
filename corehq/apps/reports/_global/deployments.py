from corehq.apps.app_manager.models import Application
from corehq.apps.reports import util
from corehq.apps.reports._global import ProjectReportParametersMixin, ProjectReport
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType
from corehq.apps.reports.fields import SelectApplicationField
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import StandardTabularHQReport
from couchforms.models import XFormInstance

class DeploymentsReport(GenericTabularReport, ProjectReport, ProjectReportParametersMixin):
    """
        Base class for all deployments reports
    """

class ApplicationStatusReport(DeploymentsReport):
    name = "Application Status"
    slug = "app_status"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.GroupField',
              'corehq.apps.reports.fields.SelectApplicationField']

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn("Username"),
            DataTablesColumn("Last Seen",sort_type=DTSortType.NUMERIC),
            DataTablesColumn("CommCare Version"),
            DataTablesColumn("Application [Deployed Build]"))

    @property
    def rows(self):
        rows = []
        selected_app = self.request_params.get(SelectApplicationField.slug, '')
        for user in self.users:
            last_seen = util.format_datatables_data("Never", -1)
            version = "---"
            app_name = "---"
            is_unknown = True

            endkey = [self.domain, user.userID]
            startkey = [self.domain, user.userID, {}]
            data = XFormInstance.view("reports/last_seen_submission",
                startkey=startkey,
                endkey=endkey,
                include_docs=True,
                descending=True,
                reduce=False).first()

            if data:
                last_seen = util.format_relative_date(data.received_on)

                if data.version != '1':
                    build_id = data.version
                else:
                    build_id = "unknown"

                form_data = data.get_form
                try:
                    app_name = form_data['meta']['appVersion']['#text']
                    version = "2.0 Remote"
                except KeyError:
                    try:
                        app = Application.get(data.app_id)
                        is_unknown = False
                        if selected_app and selected_app != data.app_id:
                            continue
                        version = app.application_version
                        app_name = "%s [%s]" % (app.name, build_id)
                    except Exception:
                        version = "unknown"
                        app_name = "unknown"
            if is_unknown and selected_app:
                continue
            row = [user.username_in_report, last_seen, version, app_name]
            rows.append(row)
        return rows