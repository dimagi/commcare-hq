import datetime
from django.conf import settings
from django.core.management.base import LabelCommand

# OldDomain no longer exists. Should this command be removed?
#from corehq.apps.domain.models import Domain, OldDomain

class Command(LabelCommand):
    help = "Migrates old django domain model new couch model. March 2012."
    args = ""
    label = ""

    def handle(self, *args, **options):
        django_domains = OldDomain.objects.all()

        print "Migrating Domain Model from django to couch"
        for domain in django_domains:
            try:
                existing_domain = Domain.get_by_name(domain.name)
                if existing_domain:
                    couch_domain = existing_domain
                    if not couch_domain.date_created:
                        couch_domain.date_created = datetime.datetime.utcnow()
                    if not couch_domain.default_timezone:
                        couch_domain.default_timezone = getattr(settings, "TIME_ZONE", "UTC")
                else:
                    couch_domain = Domain(name=domain.name,
                                                is_active=domain.is_active)
                    couch_domain.date_created = datetime.datetime.utcnow()
                couch_domain.save()
            except Exception as e:
                print "There was an error migrating the domain named %s." % domain.name
                print "Error: %s", e
