from django_extensions.management.jobs import DailyJob
import logging

class Job(DailyJob):
    help = "Daily Report"
    def execute(self):
        # executing empty sample job
        logging.debug("Daily report")
        pass
