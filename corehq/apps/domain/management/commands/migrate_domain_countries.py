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
        #Special cases
        country_lookup["USA"] = country_lookup["united states"]
        country_lookup["California"] = country_lookup["united states"]
        country_lookup["Wales"] = country_lookup["united kingdom"]

        for domain in Domain.get_all():
            try:
                if isinstance(domain.deployment.country, basestring):
                    if ',' in domain.deployment.country:
                        countries = domain.deployment.country.split(',')
                    elif ' and ' in domain.deployment.country:
                        countries = domain.deployment.country.split(' and ')
                    else:
                        countries = [domain.deployment.country]

                    abbr = []
                    for country in countries:
                        country = country.strip().lower()
                        if country in country_lookup.keys():
                            abbr.append(country_lookup[country])

                    domain.deployment.countries = abbr
                    domain.save()
            except Exception as e:
                print "There was an error migrating the domain named %s." % domain.name
                print "Error: %s", e
