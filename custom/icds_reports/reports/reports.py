from __future__ import absolute_import
from __future__ import unicode_literals
from django.urls import reverse

from corehq import toggles
from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.filters.select import YearFilter
from corehq.apps.reports.standard import CustomProjectReport
from custom.icds_reports.asr_sqldata import ASRIdentification, ASROperationalization, ASRPopulation, Annual, \
    DisabledChildren, Infrastructure, Equipment
from custom.icds_reports.filters import ICDSMonthFilter, IcdsLocationFilter, IcdsRestrictedLocationFilter
from custom.icds_reports.mpr_sqldata import MPRIdentification, MPRSectors, MPRPopulation, MPRBirthsAndDeaths, \
    MPRAWCDetails, MPRSupplementaryNutrition, MPRUsingSalt, MPRProgrammeCoverage, MPRPreschoolEducation, \
    MPRGrowthMonitoring, MPRImmunizationCoverage, MPRVhnd, MPRReferralServices, MPRMonitoring
from custom.icds_reports.mpr_sqldata import MPROperationalization
from custom.icds_reports.reports import IcdsBaseReport
from memoized import memoized


@location_safe
class MPRReport(IcdsBaseReport):

    title = 'Monthly Progress Report (MPR)'
    slug = 'mpr_report'
    name = 'MPR'

    fields = [IcdsLocationFilter, ICDSMonthFilter, YearFilter]

    @property
    def data_provider_classes(self):
        return [
            MPRIdentification,
            MPROperationalization,
            MPRSectors,
            MPRPopulation,
            MPRBirthsAndDeaths,
            MPRAWCDetails,
            MPRSupplementaryNutrition,
            MPRUsingSalt,
            MPRProgrammeCoverage,
            MPRPreschoolEducation,
            MPRGrowthMonitoring,
            MPRImmunizationCoverage,
            MPRVhnd,
            MPRReferralServices,
            MPRMonitoring
        ]


@location_safe
class ASRReport(IcdsBaseReport):

    title = 'Annual Status Report (ASR)'
    slug = 'asr_report'
    name = 'ASR'

    fields = [IcdsRestrictedLocationFilter]

    @property
    def data_provider_classes(self):
        cls_list = [
            ASRIdentification,
            ASROperationalization,
            ASRPopulation,
            Annual,
            DisabledChildren,
            Infrastructure,
            Equipment
        ]
        return cls_list


@location_safe
class DashboardReport(CustomProjectReport):
    slug = 'dashboard_report'
    name = 'Dashboard ICDS-CAS'

    @classmethod
    def get_url(cls, domain=None, **kwargs):
        return reverse('icds_dashboard', args=[domain])

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return toggles.DASHBOARD_ICDS_REPORT.enabled(domain)
