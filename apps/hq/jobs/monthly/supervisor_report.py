from django_extensions.management.jobs import MonthlyJob
import hq.reporter as reporter

class Job(MonthlyJob):
    help = "Supervisor Monthly Report Job."

    def _doEmailReports(self):
        pass


    def _doSMSReports(self):
        pass

    def execute(self):
        reporter.run_reports('monthly')

