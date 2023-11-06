from django.test import TestCase

from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.migration_utils import (
    repair_repeaters_with_whitelist_bug,
)
from corehq.motech.repeaters.models import FormRepeater


class TestRepairRepeatersWithWhitelistBug(TestCase):
    """
    The whitelist bug resulted in the white_listed_form_xmlns key in a
    repeater's option storing '[]' as a form id it would whitelist.
    """
    def test_properly_configured_repeater_is_ignored(self):
        repeater = FormRepeater.objects.create(
            domain='test',
            connection_settings=self.connection_settings,
            name='properly-configured-repeater',
            options={'white_listed_form_xmlns': ['abc123']}
        )

        fixed_ids = repair_repeaters_with_whitelist_bug()

        refetched_repeater = FormRepeater.objects.get(id=repeater.repeater_id)
        self.assertEqual(refetched_repeater.options['white_listed_form_xmlns'], ['abc123'])
        self.assertEqual(fixed_ids, [])

    def test_impacted_repeater_is_fixed(self):
        repeater = FormRepeater.objects.create(
            domain='test',
            connection_settings=self.connection_settings,
            name='repeater-with-bug',
            options={'white_listed_form_xmlns': ['[]']}
        )

        fixed_ids = repair_repeaters_with_whitelist_bug()

        refetched_repeater = FormRepeater.objects.get(id=repeater.repeater_id)
        self.assertEqual(refetched_repeater.options['white_listed_form_xmlns'], [])
        self.assertEqual(fixed_ids, [repeater.repeater_id])

    def test_impacted_but_deleted_repeater_is_fixed(self):
        repeater = FormRepeater.objects.create(
            domain='test',
            connection_settings=self.connection_settings,
            name='deletd-repeater-with-bug',
            options={'white_listed_form_xmlns': ['[]']},
            is_deleted=True,
        )

        fixed_ids = repair_repeaters_with_whitelist_bug()

        refetched_repeater = FormRepeater.all_objects.get(id=repeater.repeater_id)
        self.assertEqual(refetched_repeater.options['white_listed_form_xmlns'], [])
        self.assertEqual(fixed_ids, [repeater.repeater_id])

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        conn = ConnectionSettings(
            domain='test',
            name="repeaters-bug-settings",
            url="url",
        )
        conn.save()
        cls.connection_settings = conn
