from corehq.apps.groups.models import Group
from corehq.apps.reports.custom import ReportField, ReportSelectField
from corehq.apps.reports.fields import SelectMobileWorkerField, SelectFilteredMobileWorkerField
from corehq.apps.fixtures.models import FixtureDataType, FixtureDataItem
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
    domain = 'hsph'
    slugs = dict(site="hsph_site",
            district="hsph_district",
            region="hsph_region")
    template = "hsph/fields/sites.html"

    def update_context(self):
        sites = self.getFacilities()
        self.context['sites'] = sites
        self.context['selected'] = dict(region=self.request.GET.get(self.slugs['region'], ''),
                                        district=self.request.GET.get(self.slugs['district'], ''),
                                        siteNum=self.request.GET.get(self.slugs['site'], ''))
        self.context['slugs'] = self.slugs

    @classmethod
    def getFacilities(cls):
        facs = dict()
        data_type = FixtureDataType.by_domain_tag(cls.domain, 'site').first()
        key = [cls.domain, data_type._id]
        fixtures = get_db().view('fixtures/data_items_by_domain_type',
            startkey=key,
            endkey=key+[{}],
            reduce=False,
            include_docs=True
        ).all()
        for fix in fixtures:
            fix = FixtureDataItem.wrap(fix["doc"])
            print fix
            print fix.fields
            region = fix.fields.get("region_id")
            district = fix.fields.get("district_id")
            site = fix.fields.get("site_number")
            if region not in facs:
                facs[region] = dict(name=fix.fields.get("region_name"), districts=dict())
            if district not in facs[region]["districts"]:
                facs[region]["districts"][district] = dict(name=fix.fields.get("district_name"), sites=dict())
            if site not in facs[region]["districts"][district]["sites"]:
                facs[region]["districts"][district]["sites"][site] = dict(name=fix.fields.get("site_name"))
        return facs

class NameOfDCOField(SelectFilteredMobileWorkerField):
    slug = "dco_name"
    name = "Name of DCO"
    group_names = ["DCO"]

class NameOfDCCField(SelectFilteredMobileWorkerField):
    slug = "dcc_name"
    name = "Name of DCC"
    group_names = ["DCC"]

class NameOfCITLField(SelectFilteredMobileWorkerField):
    slug = "citl_name"
    name = "Name of CITL"
    group_names = ["CITL"]


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

class IHForCHFField(ReportSelectField):
    slug = "ihf_or_chf"
    name = "IHF/CHF"
    cssId = "hsph_ihf_or_chf"
    cssClasses = "span2"
    options = [dict(val="IHF", text="IHF"),
               dict(val="CHF", text="CHF")]
    default_option = "Select IHF/CHF..."


class FacilityStatusField(ReportSelectField):
    slug = "facility_status"
    name = "Facility Status"
    cssId = "hsph_facility_status"
    cssClasses = "span4"
    options = [dict(val="-1", text="On Board"),
               dict(val="0", text="S.B.R. Deployed"),
               dict(val="1", text="Baseline"),
               dict(val="2", text="Trial Data")]
    default_option = "Select Status..."