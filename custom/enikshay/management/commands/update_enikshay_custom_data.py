from django.core.management.base import BaseCommand
from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition, CustomDataField
from corehq.apps.locations.views import LocationFieldsView
from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView

# pcp -> MBBS
# pac -> AYUSH/other
# plc -> Private Lab
# pcc -> pharmacy / chemist

LOCATION_FIELDS = [
    # (slug, label, choices)
    ('private_sector_org_id', "Private Sector Org ID", []),
    ('suborganization', "Suborganization", ["MGK", "Alert"]),
]

USER_FIELDS = [
    ('tb_corner', "TB Corner", ["Yes", "No"]),
    ('mbbs_qualification', "MBBS Qualification", ["MBBS", "DTCD", "MD - Chest Physician",
                                                  "MD - Medicine", "MS", "DM"]),
    ('ayush_qualification', "AYUSH Qualification", ["BAMS", "BHMS", "BUMS", "DAMS", "DHMS", "ASHA",
                                                    "ANM", "GNM", "LCEH", "NGO", "Others", "None"]),
    ('professional_org_membership', "Professional Org Membership", ["IMA", "WMA", "AMA", "AAFP",
                                                                    "Others", "None"]),
]


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def show(self, definition):
        for field in definition.fields:
            print " ", field.slug

    def confirm(self):
        return raw_input("Continue?\n(y/n)") == 'y'

    def handle(self, domain, **options):
        self.user_data = CustomDataFieldsDefinition.get_or_create(
            domain, UserFieldsView.field_type)
        self.location_data = CustomDataFieldsDefinition.get_or_create(
            domain, LocationFieldsView.field_type)

        print "\nOLD:"
        self.show(self.user_data)
        self.update_definition(self.user_data, USER_FIELDS)
        print "\nNEW:"
        self.show(self.user_data)
        if self.confirm():
            self.user_data.save()

        print "\nOLD:"
        self.show(self.location_data)
        self.update_definition(self.location_data, LOCATION_FIELDS)
        print "\nNEW:"
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
            )
            for slug, label, choices in spec
        ]
