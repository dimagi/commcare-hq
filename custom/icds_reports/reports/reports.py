from custom.icds_reports.asr_sqldata import ASRIdentification, ASROperationalization, ASRPopulation
from custom.icds_reports.mpr_sqldata import MPRIdentification, MPRSectors, MPRPopulation, MPRBirthsAndDeaths, \
    MPRAWCDetails, MPRSupplementaryNutrition, MPRUsingSalt, MPRProgrammeCoverage, MPRPreschoolEducation, \
    MPRGrowthMonitoring, MPRImmunizationCoverage, MPRVhnd, MPRReferralServices, MPRMonitoring
from custom.icds_reports.mpr_sqldata import MPROperationalization
from custom.icds_reports.reports import IcdsBaseReport
from dimagi.utils.decorators.memoized import memoized


class MPRReport(IcdsBaseReport):

    title = 'Block MPR'
    slug = 'mpr_report'
    name = 'Block MPR'

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


class ASRReport(IcdsBaseReport):

    title = 'Block ASR'
    slug = 'asr_report'
    name = 'Block ASR'

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        return [
            ASRIdentification(config=config),
            ASROperationalization(config=config),
            ASRPopulation(config=config),

        ]