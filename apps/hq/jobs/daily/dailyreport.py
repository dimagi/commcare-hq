from django_extensions.management.jobs import DailyJob
import hq.reporter as reporter

class Job(DailyJob):
    help = "Organization Daily Report Job."

    def _doEmailReports(self):
        pass


    def _doSMSReports(self):
        pass

    def execute(self):
        reporter.run_reports('daily')

