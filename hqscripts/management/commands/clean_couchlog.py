from django.core.management.base import BaseCommand
from couchlog.models import ExceptionRecord


class Command(BaseCommand):
    """
    Deletes sofabed cruft from couchlog.
    """
    help = "Deletes sofabed cruft from couchlog."
    args = ""
    label = ""

    def handle(self, *args, **options):
        all_matching_records = ExceptionRecord.view("couchlog/all_by_msg", 
                                 startkey="problem in form listener",
                                 endkey="problem in form listenerz",
                                 reduce=False).all()
        for row in all_matching_records:
            ExceptionRecord.get_db().delete_doc(row["id"])
