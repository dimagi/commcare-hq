from django.core.urlresolvers import reverse

from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.filters.select import YearFilter
from corehq.apps.reports.standard import CustomProjectReport
from custom.icds_reports.asr_sqldata import ASRIdentification, ASROperationalization, ASRPopulation, Annual, \
    DisabledChildren, Infrastructure, Equipment
from custom.icds_reports.filters import ICDSMonthFilter, IcdsLocationFilter
from custom.icds_reports.mpr_sqldata import MPRIdentification, MPRSectors, MPRPopulation, MPRBirthsAndDeaths, \
    MPRAWCDetails, MPRSupplementaryNutrition, MPRUsingSalt, MPRProgrammeCoverage, MPRPreschoolEducation, \
    MPRGrowthMonitoring, MPRImmunizationCoverage, MPRVhnd, MPRReferralServices, MPRMonitoring
from custom.icds_reports.mpr_sqldata import MPROperationalization
from custom.icds_reports.reports import IcdsBaseReport
from dimagi.utils.decorators.memoized import memoized


@location_safe
class MPRReport(IcdsBaseReport):

    title = '1. Identification and Basic Information'
    slug = 'mpr_report'
    name = 'Block MPR'

    fields = [AsyncLocationFilter, ICDSMonthFilter, YearFilter]

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        return [
            MPRIdentification(config=config),
            MPROperationalization(config=config),
            MPRSectors(config=config),
            MPRPopulation(config=config),
            MPRBirthsAndDeaths(config=config),
            MPRAWCDetails(config=config),
            MPRSupplementaryNutrition(config=config),
            MPRUsingSalt(config=config),
            MPRProgrammeCoverage(config=config),
            MPRPreschoolEducation(config=config),
            MPRGrowthMonitoring(config=config),
            MPRImmunizationCoverage(config=config),
            MPRVhnd(config=config),
            MPRReferralServices(config=config),
            MPRMonitoring(config=config)
        ]


@location_safe
class ASRReport(IcdsBaseReport):

    title = '1. Identification and Basic Information'
    slug = 'asr_report'
    name = 'Block ASR'

    fields = [IcdsLocationFilter]

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        return [
            ASRIdentification(config=config),
            ASROperationalization(config=config),
            ASRPopulation(config=config),
            Annual(config=config),
            DisabledChildren(config=config),
            Infrastructure(config=config),
            Equipment(config=config)
        ]


@location_safe
class TableauReport(CustomProjectReport):

    slug = 'tableau_dashboard'
    name = 'ICDS-CAS Dashboard'

    @classmethod
    def get_url(cls, domain=None, **kwargs):
        domain_to_workbook_mapping = {
            'icds-test': 'DashboardTest',
            'icds-cas': 'DashboardR5',
        }
        workbook_name = domain_to_workbook_mapping.get(domain, domain_to_workbook_mapping['icds-cas'])
        worksheet_name = 'Dashboard'
        return reverse('icds_tableau', args=[domain, workbook_name, worksheet_name])
