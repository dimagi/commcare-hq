from django.core.management.base import BaseCommand, CommandError
from corehq.apps.users.models import CouchUser


class Command(BaseCommand):
    help = "Syncs the users in a domain from CouchDB to PostgresSQL."
    args = '<domain>'

    def handle(self, *args, **options):
        if len(args) != 1:
            raise CommandError('Usage is sync_couch_users_to_sql %s' % self.args)

        domain = args[0].strip()

        users = CouchUser.by_domain(domain)
        for user in users:
            user.save()