from corehq.apps.adm.reports import DefaultReportADMSectionView

class SupervisorReportsADMSection(DefaultReportADMSectionView):
    name = "Supervisor Reports"
    slug = "supervisor"
    asynchronous = True
    mobile_enabled = True

    adm_slug = "supervisor"



