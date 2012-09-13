from corehq.apps.reports.fields import ReportField, ReportSelectField
from corehq.apps.reports.fields import SelectMobileWorkerField, SelectFilteredMobileWorkerField
from corehq.apps.fixtures.models import FixtureDataType, FixtureDataItem


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
        fixtures = FixtureDataItem.by_data_type(cls.domain, data_type.get_id)
        for fix in fixtures:
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

class NameOfDCTLField(ReportSelectField):
    slug = "dctl_name"
    name = "Name of DCTL"
    domain = 'hsph'
    default_option = "All DCTLs..."
    cssClasses = "span3"

    def update_params(self):
        super(NameOfDCTLField, self).update_params()
        self.options = self.get_dctl_list()

    @classmethod
    def get_dctl_list(cls):
        data_type = FixtureDataType.by_domain_tag(cls.domain, 'dctl').first()
        data_items = FixtureDataItem.by_data_type(cls.domain, data_type.get_id if data_type else None)
        return [dict(text=item.fields.get("name"), val=item.fields.get("id")) for item in data_items]

    @classmethod
    def get_users_per_dctl(cls):
        dctls = dict()
        data_type = FixtureDataType.by_domain_tag(cls.domain, 'dctl').first()
        data_items = FixtureDataItem.by_data_type(cls.domain, data_type.get_id if data_type else None)
        for item in data_items:
            dctls[item.fields.get("id")] = item.get_users(wrap=False)
        return dctls

class SelectReferredInStatusField(ReportSelectField):
    slug = "referred_in_status"
    name = "Referred In Status"
    cssId = "hsph_referred_in_status"
    cssClasses = "span3"
    options = [dict(val="all", text="All Birth Data"),
               dict(val="referred", text="Only Referred In Births")]
    default_option = "Select Referred In Status"

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
    domain = 'hsph'
    cssId = "hsph_ihf_or_chf"
    cssClasses = "span2"
    options = [dict(val="IHF", text="IHF"),
               dict(val="CHF", text="CHF")]
    default_option = "Select IHF/CHF..."

    @classmethod
    def getIHFCHFFacilities(cls):
        facilities = dict(ihf=[], chf=[])
        data_type = FixtureDataType.by_domain_tag(cls.domain, 'site').first()
        data_items = FixtureDataItem.by_data_type(cls.domain, data_type.get_id)
        for item in data_items:
            facilities.get(item.fields.get("ihf_chf", "").lower(), []).append(item.fields.get("site_id"))
        return facilities


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



class FacilityField(ReportSelectField):
    slug = "facility"
    domain = 'hsph'
    name = "Facility"
    cssId = "hsph_facility_name"
    default_option = "All Facilities..."
    cssClasses = "span3"

    def update_params(self):
        super(FacilityField, self).update_params()
        self.options = self.getFacilties()

    @classmethod
    def getFacilties(cls):
        data_type = FixtureDataType.by_domain_tag(cls.domain, 'site').first()
        data_items = FixtureDataItem.by_data_type(cls.domain, data_type.get_id)
        return [dict(text=item.fields.get("site_name"), val=item.fields.get("site_id")) for item in data_items]
