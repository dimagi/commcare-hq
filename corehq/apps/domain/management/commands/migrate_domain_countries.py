from __future__ import print_function
from __future__ import absolute_import
from django.core.management.base import BaseCommand
from django_countries.data import COUNTRIES
from corehq.apps.domain.models import Domain
import six


class Command(BaseCommand):
    help = "Migrates old django domain countries from string to list. Sept 2014."

    def handle(self, **options):
        print("Migrating Domain countries")

        country_lookup = {v.lower(): k for k, v in six.iteritems(COUNTRIES)}
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
                        if country in country_lookup:
                            abbr.append(country_lookup[country])

                    domain.deployment.countries = abbr
                    domain.save()
            except Exception as e:
                print("There was an error migrating the domain named %s." % domain.name)
                print("Error: %s" % e)
