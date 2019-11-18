from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CouchUser


class Command(BaseCommand):
    help = "Sets all dimagi account created projects as non-self-started"

    @staticmethod
    def get_dimagi_account_users():
        return User.objects.filter(username__endswith="@dimagi.com")

    @staticmethod
    def update_domain_if_self_started(domain_name, username):
        project = Domain.get_by_name(domain_name)
        if (project
                and project.creating_user
                and project.creating_user == username
                and project.internal.self_started):
            print("Updating domain: {domain_name} with username: {username}".format(
                domain_name=domain_name, username=username))
            project.internal.self_started = False
            project.save()

    def handle(self, *args, **options):
        for dimagi_user in self.get_dimagi_account_users():
            couch_user = CouchUser.from_django_user(dimagi_user)
            if couch_user:
                username = dimagi_user.username
                print("username: " + username)
                for domain_name in couch_user.get_domains():
                    print("domain: " + domain_name)
                    self.update_domain_if_self_started(domain_name, username)
