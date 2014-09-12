from django.core.management.base import BaseCommand, CommandError
from corehq.apps.domain.models import Domain


class Command(BaseCommand):
    help = "Deletes the given domain and its contents"
    args = '<domain>'

    def handle(self, *args, **options):
        print "Deleting domain"
        domain = args[0].strip()
        Domain.get_by_name(domain).delete()
        print "Operation completed"
