import dateutil.parser
from corehq.apps.groups.models import Group
from corehq.apps.reports.standard import (CustomProjectReport,
    ProjectReportParametersMixin, DatespanMixin)
from corehq.apps.reports.datatables import (DataTablesColumn, DataTablesHeader,
    DTSortType)
from corehq.apps.reports.generic import GenericTabularReport
from corehq.util.timezones.conversions import ServerTime
from dimagi.utils.couch.database import get_db
from hsph.fields import (FacilityStatusField, IHForCHFField, SiteField,
    NameOfDCTLField)
from hsph.reports import HSPHSiteDataMixin
from corehq.util.timezones import utils as tz_utils

class ProjectManagementReport(CustomProjectReport, ProjectReportParametersMixin, DatespanMixin):
    """
        Base class for this set of reports
    """

class ProjectStatusDashboardReport(ProjectManagementReport):
    name = "Project Status Dashboard"
    slug = "hsph_project_status"
    fields = ['corehq.apps.reports.filters.dates.DatespanFilter',
              'hsph.fields.SiteField']
    report_template_path = "hsph/reports/project_status.html"
    flush_layout = True

    _region = None
    @property
    def region(self):
        if self._region is None:
            self._region = self.request.GET.get(SiteField.slugs['region'], None)
        return self._region

    _district = None
    @property
    def district(self):
        if self._district is None:
            self._district = self.request.GET.get(SiteField.slugs['district'], None)
        return self._district

    _site = None
    @property
    def site(self):
        if self._site is None:
            self._site = self.request.GET.get(SiteField.slugs['site'], None)
        return self._site

    @property
    def report_context(self):
        key_prefix = ["all"]
        key_suffix = []
        if self.region and self.district and self.site:
            key_prefix = ["full"]
            key_suffix = [self.region, self.district, self.site]
        elif self.region and self.district:
            key_prefix = ["district"]
            key_suffix = [self.region, self.district]
        elif self.region:
            key_prefix = ["region"]
            key_suffix = [self.region]

        facilities = IHForCHFField.get_facilities()

        ihf_data, ihf_collectors = self._gen_facility_data(key_prefix, key_suffix, facilities['ihf'])
        chf_data, chf_collectors = self._gen_facility_data(key_prefix, key_suffix, facilities['chf'])

        collectors = ihf_collectors.union(chf_collectors)
        dctls = set()

        users_per_dctls = NameOfDCTLField.get_users_per_dctl()
        for dctl, users in users_per_dctls.items():
            if len(users.intersection(collectors)) > 0:
                dctls.add(dctl)

        staff_stats = [dict(title="Number of Active Staff", val=len(collectors)+len(dctls)),
                       dict(title="DCTL", val=len(dctls))]

        for group in ["DCO", "DCP", "DCC"]:
            grp = Group.by_name(self.domain, group)
            users = set(grp.get_user_ids() if grp else [])
            staff_stats.append(dict(title=group, val=len(users.intersection(collectors))))

        citl_stat = lambda x: (float(x)/120)*100
        summary = [
            dict(title="Facilities with no status", stat=citl_stat),
            dict(title="No of facilities where S.B.R has been deployed", stat=citl_stat),
            dict(title="No. of Facilities where Baseline data collection has begun", stat=citl_stat),
            dict(title="No of Facilities where Data collection for Trial has begun", stat=citl_stat),
            dict(title="No of Birth events observed for Processes", stat=lambda x: (float(x)/2400)*100),
            dict(title="No of Outcome Data Collection Completed", stat=lambda x: (float(x)//172000)*100),
            dict(title="No of Process Data Collection Completed", stat=lambda x: (float(x)//2400)*100)]

        data = []
        for ind in range(len(summary)):
            data.append(dict(
                    title=summary[ind].get("title", ""),
                    ihf=ihf_data[ind],
                    chf=chf_data[ind],
                    total=ihf_data[ind]+chf_data[ind],
                    summary="%.2f%%" % summary[ind].get("stat", lambda x: x)(ihf_data[ind]+chf_data[ind])
                ))
        return dict(
            staff=staff_stats,
            status_data=data
        )

    def _gen_facility_data(self, key_prefix, key_suffix, facilities):
        values = ["numAtZero", "numSBR", "numBaseline", "numTrial", u'totalBirthEvents', "numOutcomeData", "numProcessData"]
        summary = dict([(val, 0) for val in values])
        active_collectors = []
        for facility in facilities:
            key = key_prefix+[facility]+key_suffix
            data = get_db().view("hsph/pm_project_status_old",
                    startkey=key+[self.datespan.startdate_param_utc],
                    endkey=key+[self.datespan.enddate_param_utc],
                    reduce=True
                ).first()
            if not data:
                data = {}
            data = data.get('value', {})
            for val in values:
                summary[val] += data.get(val, 0)
            active_collectors.extend(data.get("activeCollectors", []))
        return [item for _, item in summary.items()], set(active_collectors)

class ImplementationStatusDashboardReport(GenericTabularReport, ProjectManagementReport, HSPHSiteDataMixin):
    name = "Implementation Status Dashboard"
    slug = "hsph_implementation_status"
    fields = ['corehq.apps.reports.filters.dates.DatespanFilter',
              'hsph.fields.IHForCHFField',
              'hsph.fields.FacilityStatusField',
              'hsph.fields.NameOfCITLField',
              'hsph.fields.SiteField']

    _facility_status = None
    @property
    def facility_status(self):
        if self._facility_status is None:
            self._facility_status = self.request.GET.get(FacilityStatusField.slug)
        return self._facility_status

    _facility_type = None
    @property
    def facility_type(self):
        if self._facility_type is None:
            self._facility_type = self.request.GET.get(IHForCHFField.slug)
        return self._facility_type

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn("Status", sort_type=DTSortType.NUMERIC),
            DataTablesColumn("Region"),
            DataTablesColumn("District"),
            DataTablesColumn("IHF/CHF"),
            DataTablesColumn("CITL Name"),
            DataTablesColumn("Site"),
            DataTablesColumn("Facility Status"),
            DataTablesColumn("Status last updated on"))

    @property
    def rows(self):
        rows = []
        if not self.selected_site_map:
            self._selected_site_map = self.site_map
        site_keys = self.generate_keys()
        facilities = IHForCHFField.get_facilities()

        key_prefix = ["status"] if self.facility_status else ["all"]
        key_suffix = [self.facility_status] if self.facility_status else []

        for user in self.users:
            for site in site_keys:
                ihf_chf = '--'
                site_id = ''.join(site)
                if site_id in facilities['ihf']:
                    ihf_chf = 'IHF'
                elif site_id in facilities['chf']:
                    ihf_chf = 'CHF'

                if self.facility_type and self.facility_type != ihf_chf:
                    continue

                key = key_prefix + site + [user.user_id] + key_suffix
                data = get_db().view('hsph/pm_implementation_status_old',
                        reduce=True,
                        startkey=key+[self.datespan.startdate_param_utc],
                        endkey=key+[self.datespan.enddate_param_utc]
                    ).all()
                region, district, site = self.get_site_table_values(site)

                pb_temp = '<div class="progress"><div class="bar" style="width: %(percent)d%%;"></div></div>'

                if data:
                    for item in data:
                        item = item.get('value', {})
                        fac_stat = item.get('facilityStatus', -1)
                        try:
                            last_updated = dateutil.parser.parse(item.get('lastUpdated', "--")).replace(tzinfo=None)
                        except ValueError:
                            last_updated_str = item.get('lastUpdated', "--")
                        else:
                            last_updated_str = (
                                ServerTime(last_updated)
                                .user_time(self.timezone).ui_string()
                            )
                        rows.append([
                            self.table_cell(fac_stat, pb_temp % dict(percent=(fac_stat+2)*25)),
                            region,
                            district,
                            ihf_chf,
                            user.username_in_report,
                            site,
                            FacilityStatusField.options[fac_stat+1]['text'],
                            last_updated_str,
                        ])
        return rows
