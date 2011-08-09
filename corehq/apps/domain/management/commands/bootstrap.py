from django.core.management.base import LabelCommand, CommandError
from corehq.apps.domain.shortcuts import create_domain, create_user
from corehq.apps.users.models import CouchUser

class Command(LabelCommand):
    help = "Bootstrap a domain and user who owns it."
    args = "<domain> <user> <pass>"
    label = ""
     
    def handle(self, *args, **options):
        if len(args) != 3:
            raise CommandError('Usage: manage.py bootstrap <domain> <user> <password>')
        domain_name, username, passwd = args
        domain = create_domain(domain_name)
        user = create_user(username, passwd)
        couch_user = CouchUser.from_django_user(user)
        couch_user.add_domain_membership(domain_name, is_admin=True)
        couch_user.save()
        
        print "user %s created and added to domain %s" % (user, domain)
