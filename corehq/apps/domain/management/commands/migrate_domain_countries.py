from django.core.management.base import LabelCommand
from django_countries.countries import COUNTRIES
from corehq.apps.domain.models import Domain

class Command(LabelCommand):
    help = "Migrates old django domain countries from string to list. Sept 2014."
    args = ""
    label = ""

    def handle(self, *args, **options):
        print "Migrating Domain countries"

        country_lookup = {x[1].lower(): x[0] for x in COUNTRIES}
        for domain in Domain.get_all():
            try:
                if isinstance(domain.deployment.country, basestring):
                    if domain.deployment.country in country_lookup.keys():
                        abbr = [country_lookup[domain.deployment.country.lower()]]
                    else:
                        abbr = []
                    domain.deployment.country = abbr
                    domain.save()
            except Exception as e:
                print "There was an error migrating the domain named %s." % domain.name
                print "Error: %s", e
