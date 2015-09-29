from django.core.management.base import LabelCommand, CommandError
from corehq.apps.domain.models import Domain
from django.conf import settings


class Command(LabelCommand):
    help = "Bootstrap a domain and user who owns it."
    args = "<domain> <email> <password>"
    label = ""

    def handle(self, *args, **options):
        from corehq.apps.users.models import WebUser
        if len(args) != 3:
            raise CommandError('Usage: manage.py bootstrap <domain> <email> <password>')
        domain_name, username, passwd = args
        domain = Domain.get_or_create_with_name(domain_name, is_active=True)
        couch_user = WebUser.create(domain_name, username, passwd)
        couch_user.add_domain_membership(domain_name, is_admin=True)
        couch_user.is_superuser = True
        couch_user.is_staff = True
        couch_user.save()

        print "user %s created and added to domain %s" % (couch_user.username, domain)

        if not getattr(settings, 'BASE_ADDRESS', None):
            print ("Warning: You must set BASE_ADDRESS setting "
                   "in your localsettings.py file in order for commcare-hq "
                   "to be able to generate absolute urls. "
                   "This is necessary for a number of features.")
