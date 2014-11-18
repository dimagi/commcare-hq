from django.core.management.base import BaseCommand
from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition, CustomDataField
from corehq.apps.products.models import Product
from corehq.apps.domain.models import Domain
from dimagi.utils.couch.database import iter_docs


class Command(BaseCommand):
    """
    Create a CustomDataFieldsDefinition based on existing custom product
    information on each domain
    """

    help = ''

    def handle(self, *args, **options):
        for domain in Domain.get_all():
            if domain['commtrack_enabled']:
                fields_definition = CustomDataFieldsDefinition.get_or_create(
                    domain['name'],
                    'ProductFields'
                )

                product_ids = Product.ids_by_domain(domain['name'])

                existing_field_slugs = set(
                    [field.slug for field in fields_definition.fields]
                )
                for product in iter_docs(Product.get_db(), product_ids):
                    product_data = product.get('product_data', {})
                    for key in product_data.keys():
                        if key and key not in existing_field_slugs:
                            existing_field_slugs.add(key)
                            fields_definition.fields.append(CustomDataField(
                                slug=key,
                                label=key,
                                is_required=False
                            ))

                # Only save a definition for domains which use custom product data
                if fields_definition.fields:
                    fields_definition.save()
