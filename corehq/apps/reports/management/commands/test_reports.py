from __future__ import absolute_import
from django.core.management.base import BaseCommand
from corehq.apps.reports.tasks import daily_reports, weekly_reports


class Command(BaseCommand):
    help = "Tests sending reports. Equvalent to firing the celery tasks right NOW."
    
    def handle(self, **options):
        daily_reports()
        weekly_reports()
        
