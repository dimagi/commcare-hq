from __future__ import print_function
from __future__ import absolute_import
from django.core.management.base import BaseCommand, CommandError
from corehq.apps.domain.models import Domain
from django.conf import settings


class Command(BaseCommand):
    help = "Bootstrap a domain and user who owns it."

    def add_arguments(self, parser):
        parser.add_argument(
            'domain_name',
        )
        parser.add_argument(
            'username',
        )
        parser.add_argument(
            'passwd',
        )

    def handle(self, domain_name, username, passwd, **options):
        from corehq.apps.users.models import WebUser
        domain = Domain.get_or_create_with_name(domain_name, is_active=True, use_sql_backend=True)

        couch_user = WebUser.get_by_username(username)
        membership = None
        if couch_user:
            if not isinstance(couch_user, WebUser):
                raise CommandError('Username already in use by a non-web user')

            membership = couch_user.get_domain_membership(domain_name)
        else:
            couch_user = WebUser.create(domain_name, username, passwd)

        if not membership:
            couch_user.add_domain_membership(domain_name, is_admin=True)

        couch_user.is_superuser = True
        couch_user.is_staff = True
        couch_user.save()

        print("user %s created and added to domain %s" % (couch_user.username, domain))

        if not getattr(settings, 'BASE_ADDRESS', None):
            print ("Warning: You must set BASE_ADDRESS setting "
                   "in your localsettings.py file in order for commcare-hq "
                   "to be able to generate absolute urls. "
                   "This is necessary for a number of features.")
