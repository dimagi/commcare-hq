from django.core.management.base import LabelCommand, CommandError
from django.contrib.sites.models import Site
from django.core.exceptions import ObjectDoesNotExist

class Command(LabelCommand):
    help = "Bootstrap a domain and user who owns it."
    args = "<domain> <email> <password>"
    label = ""
     
    def handle(self, *args, **options):
        from corehq.apps.users.models import WebUser
        from corehq.apps.domain.shortcuts import create_domain
        if len(args) != 3:
            raise CommandError('Usage: manage.py bootstrap <domain> <email> <password>')
        domain_name, username, passwd = args
        domain = create_domain(domain_name)
        couch_user = WebUser.create(domain_name, username, passwd)
        couch_user.add_domain_membership(domain_name, is_admin=True)
        couch_user.is_superuser = True
        couch_user.is_staff = True
        couch_user.save()
        
        print "user %s created and added to domain %s" % (couch_user.username, domain)

        try:
            site = Site.objects.get(pk=1)
        except ObjectDoesNotExist:
            site = Site()
            site.save()
        site.name = 'localhost:8000'
        site.domain = 'localhost:8000'
        site.save()