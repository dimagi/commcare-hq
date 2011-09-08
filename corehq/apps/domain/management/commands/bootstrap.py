from django.core.management.base import LabelCommand, CommandError
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser

class Command(LabelCommand):
    help = "Bootstrap a domain and user who owns it."
    args = "<domain> <email> <password>"
    label = ""
     
    def handle(self, *args, **options):
        if len(args) != 3:
            raise CommandError('Usage: manage.py bootstrap <domain> <email> <password>')
        domain_name, username, passwd = args
        domain = create_domain(domain_name)
        couch_user = WebUser.create(domain_name, username, passwd)
        couch_user.add_domain_membership(domain_name, is_admin=True)
        couch_user.save()
        
        print "user %s created and added to domain %s" % (couch_user.username, domain)
