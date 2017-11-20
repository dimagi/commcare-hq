from __future__ import print_function
from __future__ import absolute_import
from django.core.management import BaseCommand
from django.db import connection

from corehq.apps.locations.models import SQLLocation
from custom.ilsgateway.models import GroupSummary


class Command(BaseCommand):
    """
        Find duplicated group summaries
    """

    def get_duplicated_rows(self):
        query = """
            SELECT os.location_id, title, os.date, string_agg(gs.id::text, ',') as ids
            FROM ilsgateway_groupsummary gs JOIN ilsgateway_organizationsummary os ON gs.org_summary_id=os.id
            GROUP BY os.location_id, title, os.date HAVING COUNT(gs.id) > 1;
        """

        with connection.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall()

    def handle(self, **options):
        for location_id, title, date, ids in self.get_duplicated_rows():
            ids = ids.split(',')
            sql_location = SQLLocation.objects.get(location_id=location_id)
            print("title: %s, location: %s, date: %s" % (title, sql_location.name, date))
            for pk in ids:
                gs = GroupSummary.objects.get(pk=int(pk))
                print("Group summary:", gs.org_summary_id, gs.total, gs.responded, gs.on_time, gs.complete)
