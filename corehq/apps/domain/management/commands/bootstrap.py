from django.core.management.base import LabelCommand, CommandError
from corehq.apps.domain.shortcuts import create_domain, create_user,\
    add_user_to_domain

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
        add_user_to_domain(user, domain)
        
