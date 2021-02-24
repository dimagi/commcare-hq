from corehq.apps.custom_data_fields.models import (
    CustomDataFieldsDefinition,
    CustomDataFieldsProfile,
    Field,
)
from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedAppsTest
from corehq.apps.linked_domain.updates import update_custom_data_models
from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView


class TestUpdateCustomDataFields(BaseLinkedAppsTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.definition = CustomDataFieldsDefinition(domain=cls.domain, field_type=UserFieldsView.field_type)
        cls.definition.save()
        cls.definition.set_fields([
            Field(
                slug='has_legs',
                label='Has legs',
                choices=['yes', 'no'],
            ),
            Field(
                slug='can_swim',
                label='Can swim',
                choices=['yes', 'no'],
            ),
            Field(
                slug='color',
                label='Color',
            ),
        ])
        cls.definition.save()

        cls.coral_profile = CustomDataFieldsProfile(
            name='Coral',
            fields={'has_legs': 'no', 'can_swim': 'no'},
            definition=cls.definition,
        )
        cls.coral_profile.save()

        cls.fish_profile = CustomDataFieldsProfile(
            name='Fish',
            fields={'has_legs': 'no', 'can_swim': 'yes'},
            definition=cls.definition,
        )
        cls.fish_profile.save()

    @classmethod
    def tearDownClass(cls):
        cls.definition.delete()
        super().tearDownClass()

    def test_update(self):
        # Initial update of linked domain
        update_custom_data_models(self.domain_link, limit_types=[UserFieldsView.field_type])
        model = CustomDataFieldsDefinition.objects.get(domain=self.linked_domain,
                                                       field_type=UserFieldsView.field_type)
        fields = model.get_fields()
        self.assertEqual(fields[0].slug, "has_legs")
        self.assertEqual(fields[0].label, "Has legs")
        self.assertEqual(fields[0].choices, ["yes", "no"])
        self.assertEqual(fields[1].slug, "can_swim")
        self.assertEqual(fields[2].slug, "color")

        profiles_by_name = {p.name: p for p in model.get_profiles()}
        self.assertEqual(profiles_by_name[self.coral_profile.name].fields, self.coral_profile.fields)
        self.assertEqual(profiles_by_name[self.fish_profile.name].fields, self.fish_profile.fields)

        # Add, update, and remove a profile
        lamprey_profile = CustomDataFieldsProfile(
            name='Lamprey',
            fields={'has_legs': 'no', 'can_swim': 'yes'},
            definition=self.definition,
        )
        lamprey_profile.save()
        self.fish_profile.fields = {
            'has_legs': 'no',
            'can_swim': 'no',
        }
        self.fish_profile.save()
        self.coral_profile.delete()

        update_custom_data_models(self.domain_link, limit_types=[UserFieldsView.field_type])
        model = CustomDataFieldsDefinition.objects.get(domain=self.linked_domain,
                                                       field_type=UserFieldsView.field_type)
        profiles_by_name = {p.name: p for p in model.get_profiles()}
        self.assertTrue(bool(profiles_by_name[self.coral_profile.name]))    # updating doesn't delete profiles
        self.assertEqual(profiles_by_name[self.fish_profile.name].fields, self.fish_profile.fields)
        self.assertEqual(profiles_by_name[lamprey_profile.name].fields, lamprey_profile.fields)
