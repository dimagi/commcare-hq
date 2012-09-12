from corehq.apps.adm.reports import ADMSectionView
from corehq.apps.reports.generic import GenericTabularReport

class SupervisorADMSectionView(ADMSectionView):
    """
        In the hopes that this section of ADM will extend to more than just reports...
    """
    adm_slug = "supervisor"

class SupervisorReportsADMSection(GenericTabularReport, ADMSectionView):
    name = "Supervisor Reports"
    slug = "supervisor_reports"

