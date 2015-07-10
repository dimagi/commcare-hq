from django.core.management.base import LabelCommand
from django_countries.data import COUNTRIES
from corehq.apps.domain.models import Domain

class Command(LabelCommand):
    help = "Migrates old django domain countries from string to list. Sept 2014."
    args = ""
    label = ""

    def handle(self, *args, **options):
        print "Migrating Domain countries"

        country_lookup = {v.lower(): k for k, v in COUNTRIES.iteritems()}
        #Special cases
        country_lookup["USA"] = country_lookup["united states"]
        country_lookup["California"] = country_lookup["united states"]
        country_lookup["Wales"] = country_lookup["united kingdom"]

        for domain in Domain.get_all():
            if domain.deployment._doc.get('countries', None):
                continue
            try:
                country = None
                if domain.deployment._doc.get('country', None):
                    country = domain.deployment._doc['country']
                elif domain._doc.get('country', None):
                    country = domain._doc['country']

                if country:
                    if ',' in country:
                        countries = country.split(',')
                    elif ' and ' in country:
                        countries = country.split(' and ')
                    else:
                        countries = [country]

                    abbr = []
                    for country in countries:
                        country = country.strip().lower()
                        if country in country_lookup.keys():
                            abbr.append(country_lookup[country])

                    domain.deployment.countries = abbr
                    domain.save()
            except Exception as e:
                print "There was an error migrating the domain named %s." % domain.name
                print "Error: %s" % e
