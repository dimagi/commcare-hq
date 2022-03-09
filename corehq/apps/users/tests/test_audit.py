import uuid

from django.test import SimpleTestCase

from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation
from corehq.apps.programs.models import Program
from corehq.apps.users.audit.change_messages import (
    UserChangeMessage,
    get_messages,
)
from corehq.apps.users.models_role import UserRole


class TestUserChangeMessageSlugs(SimpleTestCase):
    def _test_change_messages(self, change_message_method, args, expected_change_messages,
                              expected_formatted_message):
        if not isinstance(expected_formatted_message, list):
            expected_formatted_message = [expected_formatted_message]
        change_messages = change_message_method(*args)
        self.assertEqual(
            change_messages,
            expected_change_messages
        )
        self.assertEqual(
            list(get_messages(change_messages)),
            expected_formatted_message
        )

    def test_set_program(self):
        program_id = uuid.uuid4().hex
        program = Program(
            _id=program_id,
            name="Program Name"
        )

        self._test_change_messages(
            UserChangeMessage.program_change,
            [program],
            {
                "program": {
                    "set_program": {"id": program_id, "name": "Program Name"}
                }
            },
            f"Program: Program Name[{program_id}]"
        )

    def test_clear_program(self):
        self._test_change_messages(
            UserChangeMessage.program_change,
            [None],
            {
                "program": {
                    "clear_program": {}
                }
            },
            "Program: None"
        )

    def test_set_role(self):
        role_id = uuid.uuid4().hex
        role = UserRole(
            name="Role Name",
            couch_id=role_id
        )
        role.name = "Role Name"

        self._test_change_messages(
            UserChangeMessage.role_change,
            [role],
            {
                "role": {
                    "set_role": {"id": role.get_qualified_id(), "name": "Role Name"}
                }
            },
            f"Role: Role Name[{role.get_qualified_id()}]"
        )

    def test_clear_role(self):
        self._test_change_messages(
            UserChangeMessage.role_change,
            [None],
            {
                "role": {
                    "clear_role": {}
                }
            },
            "Role: None"
        )

    def test_remove_from_domain(self):
        domain = "test-domain"
        self._test_change_messages(
            UserChangeMessage.domain_removal,
            [domain],
            {
                "domain": {
                    "remove_from_domain": {"domain": domain}
                }
            },
            "Removed from domain 'test-domain'"
        )

    def test_add_to_domain(self):
        domain = "test-domain"
        self._test_change_messages(
            UserChangeMessage.domain_addition,
            [domain],
            {
                "domain": {
                    "add_to_domain": {"domain": domain}
                }
            },
            "Added to domain 'test-domain'"
        )

    def test_add_as_web_user(self):
        domain = "test-domain"
        self._test_change_messages(
            UserChangeMessage.added_as_web_user,
            [domain],
            {
                "domain": {
                    "add_as_web_user": {"domain": domain}
                }
            },
            "Added as web user to domain 'test-domain'"
        )

    def test_disable_with_verification(self):
        verified_by = "jamesbond@mi6.com"
        verification_mode = "007"
        self._test_change_messages(
            UserChangeMessage.two_factor_disabled_with_verification,
            [verified_by, verification_mode, None],
            {
                "two_factor": {
                    "disable_with_verification": {
                        "verified_by": verified_by,
                        "verification_mode": verification_mode
                    }
                }
            },
            'Two factor removed. Verified by: jamesbond@mi6.com, verification mode: "007"'
        )

        self._test_change_messages(
            UserChangeMessage.two_factor_disabled_with_verification,
            [verified_by, verification_mode, 3],
            {
                "two_factor": {
                    "disable_with_verification": {
                        "verified_by": verified_by,
                        "verification_mode": verification_mode
                    },
                    "disable_for_days": {"days": 3}
                }
            },
            [
                'Two factor removed. Verified by: jamesbond@mi6.com, verification mode: "007"',
                'Disabled for 3 days'
            ]
        )

    def test_reset_password(self):
        self._test_change_messages(
            UserChangeMessage.password_reset,
            [],
            {
                "password": {
                    "reset_password": {}
                }
            },
            "Password reset"
        )

    def test_activate_user(self):
        reason = "Revived"
        self._test_change_messages(
            UserChangeMessage.status_update,
            [True, reason],
            {
                "status": {
                    "activate_user": {
                        "reason": reason
                    }
                }
            },
            'User re-enabled. Reason: "Revived"'
        )

    def test_deactivate_user(self):
        reason = "Personal reasons"
        self._test_change_messages(
            UserChangeMessage.status_update,
            [False, reason],
            {
                "status": {
                    "deactivate_user": {
                        "reason": reason
                    }
                }
            },
            'User disabled. Reason: "Personal reasons"'
        )

    def test_add_phone_numbers(self):
        phone_numbers = [
            "9999999999",
            "1111111111"
        ]
        self._test_change_messages(
            UserChangeMessage.phone_numbers_added,
            [phone_numbers],
            {
                "phone_numbers": {
                    "add_phone_numbers": {
                        "phone_numbers": phone_numbers
                    }
                }
            },
            "Added phone number(s) 9999999999, 1111111111"
        )

    def test_remove_phone_numbers(self):
        phone_numbers = [
            "9999999999",
            "1111111111"
        ]
        self._test_change_messages(
            UserChangeMessage.phone_numbers_removed,
            [phone_numbers],
            {
                "phone_numbers": {
                    "remove_phone_numbers": {
                        "phone_numbers": phone_numbers
                    }
                }
            },
            "Removed phone number(s) 9999999999, 1111111111"
        )

    def test_set_profile(self):
        profile_id = uuid.uuid4().hex
        profile_name = "Profile Name"

        self._test_change_messages(
            UserChangeMessage.profile_info,
            [profile_id, profile_name],
            {
                "profile": {
                    "set_profile": {"id": profile_id, "name": "Profile Name"}
                }
            },
            f"Profile: Profile Name[{profile_id}]"
        )

    def test_clear_profile(self):
        self._test_change_messages(
            UserChangeMessage.profile_info,
            [None],
            {
                "profile": {
                    "clear_profile": {}
                }
            },
            "Profile: None"
        )

    def test_set_primary_location(self):
        location_id = uuid.uuid4().hex
        location = SQLLocation(
            name="Location Name",
            location_id=location_id
        )

        self._test_change_messages(
            UserChangeMessage.primary_location_info,
            [location],
            {
                "location": {
                    "set_primary_location": {"id": location_id, "name": "Location Name"}
                }
            },
            f"Primary location: Location Name[{location_id}]"
        )

    def test_clear_primary_location(self):
        self._test_change_messages(
            UserChangeMessage.primary_location_removed,
            [],
            {
                "location": {
                    "clear_primary_location": {}
                }
            },
            "Primary location: None"
        )

        self._test_change_messages(
            UserChangeMessage.primary_location_info,
            [None],
            {
                "location": {
                    "clear_primary_location": {}
                }
            },
            "Primary location: None"
        )

    def test_set_assigned_locations(self):
        location1_id = uuid.uuid4().hex
        location1 = SQLLocation(
            name="Location 1",
            location_id=location1_id
        )
        location2_id = uuid.uuid4().hex
        location2 = SQLLocation(
            name="Location 2",
            location_id=location2_id
        )

        self._test_change_messages(
            UserChangeMessage.assigned_locations_info,
            [[location1, location2]],
            {
                "assigned_locations": {
                    "set_assigned_locations": {
                        "locations": [{'id': location1_id, 'name': "Location 1"},
                                      {'id': location2_id, 'name': "Location 2"}]
                    }
                }
            },
            f"Assigned locations: ['Location 1[{location1_id}]', 'Location 2[{location2_id}]']"
        )

    def test_clear_assigned_locations(self):
        self._test_change_messages(
            UserChangeMessage.assigned_locations_info,
            [[]],
            {
                "assigned_locations": {
                    "clear_assigned_locations": {}
                }
            },
            "Assigned locations: []"
        )

    def test_set_groups(self):
        group1_id = uuid.uuid4().hex
        group1 = Group(
            _id=group1_id,
            name="Group 1"
        )
        group2_id = uuid.uuid4().hex
        group2 = Group(
            _id=group2_id,
            name="Group 2"
        )

        self._test_change_messages(
            UserChangeMessage.groups_info,
            [[group1, group2]],
            {
                "groups": {
                    "set_groups": {
                        "groups": [{'id': group1_id, 'name': "Group 1"},
                                   {'id': group2_id, 'name': "Group 2"}]
                    }
                }
            },
            f"Groups: ['Group 1[{group1_id}]', 'Group 2[{group2_id}]']"
        )

    def test_clear_groups(self):
        self._test_change_messages(
            UserChangeMessage.groups_info,
            [[]],
            {
                "groups": {
                    "clear_groups": {}
                }
            },
            "Groups: []"
        )

    def test_add_domain_invitation(self):
        domain = 'test-domain'
        self._test_change_messages(
            UserChangeMessage.invited_to_domain,
            [domain],
            {
                "domain_invitation": {
                    "add_domain_invitation": {"domain": 'test-domain'}
                }
            },
            "Invited to domain 'test-domain'"
        )

    def test_remove_domain_invitation(self):
        domain = 'test-domain'
        self._test_change_messages(
            UserChangeMessage.invitation_revoked_for_domain,
            [domain],
            {
                "domain_invitation": {
                    "remove_domain_invitation": {"domain": 'test-domain'}
                }
            },
            "Invitation revoked for domain 'test-domain'"
        )
