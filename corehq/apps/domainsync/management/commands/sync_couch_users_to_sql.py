from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand
from corehq.apps.users.models import CouchUser


class Command(BaseCommand):
    help = "Syncs the users in a domain from CouchDB to PostgresSQL."

    def handle(self, domain, **options):
        users = CouchUser.by_domain(domain)
        for user in users:
            user.save()
