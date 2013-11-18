from corehq.apps.reports.fields import ReportField, ReportSelectField
from corehq.apps.reports.fields import SelectFilteredMobileWorkerField
from corehq.apps.fixtures.models import FixtureDataType, FixtureDataItem
from corehq.apps.reports.filters.base import (BaseSingleOptionFilter,
    BaseDrilldownOptionFilter)
from corehq.apps.reports.filters.users import LinkedUserFilter

import hsph.const as const


class SiteField(ReportField):
    slug = "hsph_site"
    domain = 'hsph'
    slugs = dict(site="hsph_site",
            district="hsph_district",
            region="hsph_region")
    template = "hsph/fields/sites.html"

    def update_context(self):
        self.context['sites'] = self.getFacilities(domain=self.domain)
        self.context['selected'] = dict(region=self.request.GET.get(self.slugs['region'], ''),
                                        district=self.request.GET.get(self.slugs['district'], ''),
                                        siteNum=self.request.GET.get(self.slugs['site'], ''))
        self.context['slugs'] = self.slugs

    @classmethod
    def getFacilities(cls, domain=None):
        cls.domain = domain or cls.domain
        facs = dict()
        data_type = FixtureDataType.by_domain_tag(cls.domain, 'site').first()
        fixtures = FixtureDataItem.by_data_type(cls.domain, data_type.get_id_without_attributes)
        for fix in fixtures:
            region = fix.fields_without_attributes.get("region_id")
            district = fix.fields_without_attributes.get("district_id")
            site = fix.fields_without_attributes.get("site_number")
            if region not in facs:
                facs[region] = dict(name=fix.fields_without_attributes.get("region_name"), districts=dict())
            if district not in facs[region]["districts"]:
                facs[region]["districts"][district] = dict(name=fix.fields_without_attributes.get("district_name"), sites=dict())
            if site not in facs[region]["districts"][district]["sites"]:
                facs[region]["districts"][district]["sites"][site] = dict(name=fix.fields_without_attributes.get("site_name"))
        return facs


class NameOfFADAField(SelectFilteredMobileWorkerField):
    slug = "fada_name"
    name = "Name of FADA"
    group_names = [const.FADA_GROUP_NAME]
    cssId = "fada_name"
    show_only_group_option = False
    default_option = "All FADAs"


class NameOfFIDAField(SelectFilteredMobileWorkerField):
    slug = "fida_name"
    name = "Name of FIDA"
    group_names = [const.FIDA_GROUP_NAME]
    cssId = "fida_name"
    show_only_group_option = False
    default_option = "All FIDAs"

class NameOfCATIField(SelectFilteredMobileWorkerField):
    slug = "cati_name"
    name = "Name of CATI"
    cssId = "cati_name"
    group_names = [const.CATI_GROUP_NAME]
    show_only_group_option = False
    default_option = "All CATIs"

class NameOfCATITLField(SelectFilteredMobileWorkerField):
    slug = "cati_tl_name"
    name = "Name of CATI TL"
    cssId = "cati_tl_name"
    group_names = [const.CATI_TL_GROUP_NAME]
    show_only_group_option = False
    default_option = "All CATI TLs"
    

class NameOfCITLField(SelectFilteredMobileWorkerField):
    slug = "citl_name"
    name = "Name of CITL"
    cssId = "citl_name"
    group_names = ["CITL"]

class NameOfDCTLField(ReportSelectField):
    slug = "dctl_name"
    name = "Name of DCTL"
    cssId = "dctl_name"
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
        return [dict(text=item.fields_without_attributes.get("name"), val=item.fields_without_attributes.get("id")) for item in data_items]

    @classmethod
    def get_users_per_dctl(cls):
        dctls = dict()
        data_type = FixtureDataType.by_domain_tag(cls.domain, 'dctl').first()
        data_items = FixtureDataItem.by_data_type(cls.domain, data_type.get_id if data_type else None)
        for item in data_items:
            dctls[item.fields_without_attributes.get("id")] = item.get_users(wrap=False)
        return dctls


class DCTLToFIDAFilter(LinkedUserFilter):
    domain = 'hsph'
    user_types = ("DCTL", "FIDA")

class AllocatedToFilter(BaseSingleOptionFilter):
    slug = "allocated_to"
    label = "Allocated To"
    cssId = 'allocated_to'
    cssClasses = "span2"

    options = [
        ('cati', 'CATI'),
        ('field', 'Field')
    ]
    default_text = "All"


class SelectReferredInStatusField(ReportSelectField):
    slug = "referred_in_status"
    name = "Referred In Status"
    cssId = "hsph_referred_in_status"
    cssClasses = "span3"
    options = [dict(val="referred", text="Only Referred In Births")]
    default_option = "All Birth Data"


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
    options = [dict(val="IHF", text="IHF only"),
               dict(val="CHF", text="CHF only")]
    default_option = "IHF and CHF"

    @classmethod
    def _get_facilities(cls, domain=None):
        domain = domain or cls.domain
        facilities = dict(ihf=[], chf=[])
        data_type = FixtureDataType.by_domain_tag(domain, 'site').first()
        data_items = FixtureDataItem.by_data_type(domain, data_type.get_id)
        for item in data_items:
            ihf_chf = item.fields_without_attributes.get("ihf_chf", "").lower()
            if ihf_chf == 'ifh':  # typo in some test data
                ihf_chf = 'ihf'

            try:
                facilities[ihf_chf].append(item.fields_without_attributes)
            except KeyError:
                # there's a site fixture item without an IHF/CHF value
                pass

        return facilities

    @classmethod
    def get_facilities(cls, domain=None):
        domain = domain or cls.domain
        return dict([(ihf_chf, map(lambda f: f['site_id'], facilities))
                     for (ihf_chf, facilities)
                     in cls._get_facilities(domain).items()])

    @classmethod
    def get_selected_facilities(cls, site_map, domain=None):
        domain = domain or cls.domain
        def filter_by_sitefield(facilities):
            ret = []

            for f in facilities:
                region_id = f['region_id']
                if region_id not in site_map:
                    continue

                district_id = f['district_id']
                districts = site_map[region_id]['districts']
                if district_id not in districts:
                    continue

                site_number = f['site_number']
                if site_number in districts[district_id]['sites']:
                    ret.append(f['site_id'])
            return ret

        return dict([(ihf_chf.lower(), filter_by_sitefield(facilities))
                     for (ihf_chf, facilities)
                     in cls._get_facilities(domain).items()])


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
        self.options = self.getFacilities()

    @classmethod
    def getFacilities(cls, domain=None):
        domain = domain or cls.domain
        data_type = FixtureDataType.by_domain_tag(domain, 'site').first()
        data_items = FixtureDataItem.by_data_type(domain, data_type.get_id)
        return [dict(text=item.fields_without_attributes.get("site_name"), val=item.fields_without_attributes.get("site_id")) for item in data_items]
