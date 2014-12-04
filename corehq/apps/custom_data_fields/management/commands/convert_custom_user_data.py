from django.core.management.base import BaseCommand
from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition, CustomDataField
from corehq.apps.users.models import CommCareUser
from corehq.apps.domain.models import Domain
from dimagi.utils.couch.database import iter_docs


class Command(BaseCommand):
    """
    Create a CustomDataFieldsDefinition based on existing custom user
    information on each domain
    """

    help = ''

    def handle(self, *args, **options):
        for domain in Domain.get_all_names():
            fields_definition = CustomDataFieldsDefinition.get_or_create(
                domain,
                'UserFields'
            )

            user_ids = (CommCareUser.ids_by_domain(domain) +
                        CommCareUser.ids_by_domain(domain, is_active=False))

            existing_field_slugs = set([field.slug for field in fields_definition.fields])
            for user in iter_docs(CommCareUser.get_db(), user_ids):
                user_data = user.get('user_data', {})
                for key in user_data.keys():
                    if key and key not in existing_field_slugs:
                        existing_field_slugs.add(key)
                        fields_definition.fields.append(CustomDataField(
                            slug=key,
                            label=key,
                            is_required=False
                        ))

            # Only save a definition for domains which use custom user data
            if fields_definition.fields:
                fields_definition.save()
