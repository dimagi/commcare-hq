from __future__ import absolute_import, print_function

from __future__ import unicode_literals

from django.core.management.base import BaseCommand

from django.db import connections, transaction
from corehq.sql_db.routers import db_for_read_write
from custom.icds_reports.models import ChildHealthMonthly


TABLENAME = "config_report_icds-cas_static-child_health_cases_a46c129f"
CHUNK_SIZE = 10000
TIMES = 10


def get_cursor(model):
    db = db_for_read_write(model)
    return connections[db].cursor()


class Command(BaseCommand):
    def handle(self, *args, **options):
        t = 0
        while t < TIMES:
            with transaction.atomic():
                with get_cursor(ChildHealthMonthly) as cursor:
                    cursor.execute(
                        "SELECT * INTO TEMP tmp_blah FROM ONLY \"{tablename}\" LIMIT {chunk_size}".format(
                            tablename=TABLENAME, chunk_size=CHUNK_SIZE))
                    cursor.execute(
                        "DELETE FROM \"{tablename}\" WHERE doc_id IN (SELECT doc_id FROM tmp_blah)".format(
                            tablename=TABLENAME))
                    cursor.execute(
                        "INSERT INTO \"{tablename}\" SELECT * FROM tmp_blah".format(tablename=TABLENAME))
                    cursor.execute("DROP TABLE tmp_blah")
            t += 1
