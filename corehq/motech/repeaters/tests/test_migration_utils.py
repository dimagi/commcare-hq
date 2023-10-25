from django.test import TestCase

from corehq.motech.repeaters.models import Repeater
from corehq.motech.repeaters.migration_utils import repair_repeaters_with_whitelist_bug


class TestRepairRepeatersWithWhitelistBug(TestCase):
    """
    The whitelist bug resulted in the white_listed_form_xmlns key in a
    repeater's option storing '[]' as a form id it would whitelist.
    """
    def test_properly_configured_repeater_is_ignored(self):
        repeater = Repeater.objects.create(
            domain='test',
            repeater_id='abc123',
            name='properly-configured-repeater',
            options={'white_listed_form_xmlns': ['abc123']}
        )

        fixed_ids = repair_repeaters_with_whitelist_bug()

        self.assertEqual(repeater.options, ['abc123'])
        self.assertEqual(fixed_ids, [])

    def test_impacted_repeater_is_fixed(self):
        repeater = Repeater.objects.create(
            domain='test',
            repeater_id='abc123',
            name='properly-configured-repeater',
            options={'white_listed_form_xmlns': ['[]']}
        )

        fixed_ids = repair_repeaters_with_whitelist_bug()

        self.assertEqual(repeater.options, [])
        self.assertEqual(fixed_ids, [repeater.repeater_id])

    def test_impacted_but_deleted_repeater_is_fixed(self):
        repeater = Repeater.objects.create(
            domain='test',
            repeater_id='abc123',
            name='properly-configured-repeater',
            options={'white_listed_form_xmlns': ['[]']},
            is_deleted=True,
        )

        fixed_ids = repair_repeaters_with_whitelist_bug()

        self.assertEqual(repeater.options, [])
        self.assertEqual(fixed_ids, [repeater.repeater_id])
