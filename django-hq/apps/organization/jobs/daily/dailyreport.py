from django_extensions.management.jobs import BaseJob

class ReportJob(BaseJob):
    help = "Daily Report"





    def execute(self):
        # executing empty sample job
        pass
