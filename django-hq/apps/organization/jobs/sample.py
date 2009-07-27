from django_extensions.management.jobs import BaseJob

class Job(BaseJob):
    help = "My sample job."

    def _doEmailReport(self):
        pass


    def _doSMSReport(self):
        pass


    def execute(self):
    	# executing empty sample job
    	pass
