from __future__ import absolute_import
from __future__ import print_function
from django.core.management.base import BaseCommand
from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition, CustomDataField
from corehq.apps.locations.views import LocationFieldsView
from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView
from custom.enikshay.const import AGENCY_USER_FIELDS, AGENCY_LOCATION_FIELDS
from six.moves import input


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def show(self, definition):
        for field in definition.fields:
            print(" ", field.slug)

    def confirm(self):
        return input("Continue?\n(y/n)") == 'y'

    def handle(self, domain, **options):
        self.user_data = CustomDataFieldsDefinition.get_or_create(
            domain, UserFieldsView.field_type)
        self.location_data = CustomDataFieldsDefinition.get_or_create(
            domain, LocationFieldsView.field_type)

        print("\nOLD:")
        self.show(self.user_data)
        self.update_definition(self.user_data, AGENCY_USER_FIELDS)
        print("\nNEW:")
        self.show(self.user_data)
        if self.confirm():
            self.user_data.save()

        print("\nOLD:")
        self.show(self.location_data)
        self.update_definition(self.location_data, AGENCY_LOCATION_FIELDS)
        print("\nNEW:")
        self.show(self.location_data)
        if self.confirm():
            self.location_data.save()

    def update_definition(self, definition, fields_spec):
        existing = {field.slug for field in definition.fields}
        for field in self.get_fields(fields_spec):
            if field.slug not in existing:
                definition.fields.append(field)

    def get_fields(self, spec):
        return [
            CustomDataField(
                slug=slug,
                is_required=False,
                label=label,
                choices=choices,
                is_multiple_choice=bool(choices),
            )
            for slug, label, choices in spec
        ]
