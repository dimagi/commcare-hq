from corehq.apps.reports.custom import ReportField
from corehq.apps.reports.fields import SelectCHWField
from dimagi.utils.couch.database import get_db

class FacilityField(ReportField):
    slug = "facility"
    template = "hsph/fields/facility_name.html"

    def update_context(self):
        facilities = self.getFacilties()
        self.context['facilities'] = facilities
        self.context['selected_facility'] = self.request.GET.get(self.slug, '')
        self.context['slug'] = self.slug

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
            for site in data:
                site = site.get('key', None)
                if site:
                    region = site[0]
                    district = site[1]
                    site_num = site[2]
                    if region not in sites:
                        sites[region] = {}
                    if district not in sites[region]:
                        sites[region][district] = []
                    if site_num not in sites[region][district]:
                        sites[region][district].append(site_num)
        return sites

class NameOfDCOField(SelectCHWField):
    slug = "dco_name"
    template = "reports/fields/select_chw.html"

    def update_context(self):
        super(NameOfDCOField, self).update_context()
        self.context['field_name'] = "Name of DCO"
        self.context['default_option'] = "All DCOs"


class NameOfDCTLField(ReportField):
    slug = "dctl_name"
    template = "hsph/fields/dctl_name.html"
    dctl_list = ["DCTL Unknown"]

    def update_context(self):
        self.context["dctls"] = self.dctl_list
        self.context["slug"] = self.slug
        self.context["selected_dctl"] = self.request.GET.get(self.slug, '')