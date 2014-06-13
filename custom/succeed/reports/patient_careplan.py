from custom.succeed.reports import PM_APP_PM_MODULE, PM3, PM4
from custom.succeed.reports.patient_details import PatientDetailsReport

class PatientCarePlanReport(PatientDetailsReport):
    slug = "patient_careplan"
    name = 'Patient Care Plan'

    @property
    def report_context(self):
        self.report_template_path = "patient_plan.html"
        ret = super(PatientCarePlanReport, self).report_context
        ret['view_mode'] = 'plan'
        return ret