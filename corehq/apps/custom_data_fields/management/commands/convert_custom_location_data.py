from django.core.management.base import BaseCommand
from corehq.apps.custom_data_fields import models as cdm
from corehq.apps.locations.models import Location
from corehq.apps.domain.models import Domain
from dimagi.utils.couch.database import iter_docs


class Command(BaseCommand):
    """
    Create a CustomDataFieldsDefinition based on existing custom location
    information on each domain
    """

    help = ''

    def handle(self, *args, **options):
        for domain in Domain.get_all_names():
            fields_definition = cdm.CustomDataFieldsDefinition.get_or_create(
                domain,
                'LocationFields'
            )
            had_fields = bool(fields_definition.fields)

            existing_field_slugs = set([field.slug for field in fields_definition.fields])
            for location in Location.by_domain(domain):
                location_data = location.metadata
                for key in location_data.keys():
                    if (key and key not in existing_field_slugs
                        and not cdm.is_system_key(key)):
                        existing_field_slugs.add(key)
                        fields_definition.fields.append(cdm.CustomDataField(
                            slug=key,
                            label=key,
                            is_required=False,
                        ))

            for field in fields_definition.fields:
                if cdm.is_system_key(field.slug):
                    fields_definition.fields.remove(field)
            # Only save a definition for domains which use custom location data
            if fields_definition.fields or had_fields:
                fields_definition.save()
            print 'finished domain "{}"'.format(domain)
