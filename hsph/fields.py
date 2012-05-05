from corehq.apps.groups.models import Group
from corehq.apps.reports.custom import ReportField, ReportSelectField
from corehq.apps.reports.fields import SelectMobileWorkerField, SelectFilteredMobileWorkerField
from dimagi.utils.couch.database import get_db

class FacilityField(ReportField):
    slug = "facility"
    template = "hsph/fields/facility_name.html"

    def update_context(self):
        facilities = self.getFacilties()
        self.context['facilities'] = facilities
        self.context['selected_facility'] = self.request.GET.get(self.slug, '')

    @classmethod
    def getFacilties(cls):
        try:
            data = get_db().view('hsph/facilities',
                reduce=True,
                group=True
            ).all()
            return [item.get('key','') for item in data]
        except KeyError:
            return []

class SiteField(ReportField):
    slug = "hsph_site"
    slugs = dict(site="hsph_site",
            district="hsph_district",
            region="hsph_region")
    template = "hsph/fields/sites.html"

    def update_context(self):
        sites = self.getSites()
        self.context['sites'] = sites
        self.context['selected'] = dict(region=self.request.GET.get(self.slugs['region'], ''),
                                        district=self.request.GET.get(self.slugs['district'], ''),
                                        siteNum=self.request.GET.get(self.slugs['site'], ''))
        self.context['slug'] = self.slugs

    @classmethod
    def getSites(cls):
        sites = {}
        data = get_db().view('hsph/site_info',
            reduce=True,
            group=True
        ).all()
        if data:
            for item in data:
                site = item.get('key', None)
                if site:
                    region = site[0]
                    district = site[1]
                    site_num = site[2]
                    if region not in sites:
                        sites[region] = {}
                    if district not in sites[region]:
                        sites[region][district] = {}
                    if site_num not in sites[region][district]:
                        sites[region][district][site_num] = item['value'].get('facilityName', site_num)
        return sites

class NameOfDCOField(SelectFilteredMobileWorkerField):
    slug = "dco_name"
    name = "Name of DCO"
    group_names = ["DCO"]

class NameOfDCCField(SelectFilteredMobileWorkerField):
    slug = "dcc_name"
    name = "Name of DCC"
    group_names = ["DCC"]

class NameOfDCTLField(ReportField):
    slug = "dctl_name"
    template = "hsph/fields/dctl_name.html"
    dctl_list = ["DCTL Unknown"]

    def update_context(self):
        self.context["dctls"] = self.dctl_list
        self.context["selected_dctl"] = self.request.GET.get(self.slug, '')

class SelectCaseStatusField(ReportSelectField):
    slug = "case_status"
    name = "Home Visit Status"
    cssId = "hsph_case_status"
    cssClasses = "span2"
    options = [dict(val="closed", text="CLOSED"),
               dict(val="open", text="OPEN")]
    default_option = "Select Status..."

    def update_params(self):
        self.selected = self.request.GET.get(self.slug)