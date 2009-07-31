from django_extensions.management.jobs import WeeklyJob
import hq.reporter as reporter

class Job(WeeklyJob):
    help = "Supervisor Weekly Report Job."

    def _doEmailReports(self):
        pass


    def _doSMSReports(self):
        pass

    def execute(self):
        reporter.run_reports('weekly')

