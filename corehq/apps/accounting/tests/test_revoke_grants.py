from unittest.mock import patch

from django.test import SimpleTestCase
from django_prbac.models import Role, Grant

from corehq.apps.accounting.utils import revoke_privs_for_grantees


class TestRevokePrivsForGrantees(SimpleTestCase):

    def test_specified_priv_for_grantee_is_revoked(self):
        privs_to_revoke_for_grantee = [('grantee', ['privilege'])]
        roles_by_slug = {
            'grantee': Role(slug='grantee'),
            'privilege': Role(slug='privilege'),
        }

        expected_grants = [Grant(from_role=Role(slug='grantee'), to_role=Role(slug='privilege'))]

        with patch('corehq.apps.accounting.utils.get_all_roles_by_slug', return_value=roles_by_slug),\
             patch('corehq.apps.accounting.utils.get_grants', return_value=expected_grants),\
             patch('corehq.apps.accounting.utils.delete_grants') as mock_deletegrants:
            revoke_privs_for_grantees(privs_to_revoke_for_grantee)

        mock_deletegrants.assert_called_with(expected_grants)

    def test_dry_run_does_not_delete_grants(self):
        privs_to_revoke_for_grantee = [('grantee', ['privilege'])]
        roles_by_slug = {
            'grantee': Role(slug='grantee'),
            'privilege': Role(slug='privilege'),
        }

        expected_grants = [Grant(from_role=Role(slug='grantee'), to_role=Role(slug='privilege'))]

        with patch('corehq.apps.accounting.utils.get_all_roles_by_slug', return_value=roles_by_slug),\
             patch('corehq.apps.accounting.utils.get_grants', return_value=expected_grants),\
             patch('corehq.apps.accounting.utils.delete_grants') as mock_deletegrants:
            revoke_privs_for_grantees(privs_to_revoke_for_grantee, dry_run=True)

        mock_deletegrants.assert_not_called()

    def test_no_grants_are_deleted_if_not_found(self):
        privs_to_revoke_for_grantee = [('grantee', ['privilege'])]
        roles_by_slug = {
            'grantee': Role(slug='grantee'),
            'privilege': Role(slug='privilege'),
        }

        expected_grants = []

        with patch('corehq.apps.accounting.utils.get_all_roles_by_slug', return_value=roles_by_slug),\
             patch('corehq.apps.accounting.utils.get_grants', return_value=expected_grants),\
             patch('corehq.apps.accounting.utils.delete_grants') as mock_deletegrants:
            revoke_privs_for_grantees(privs_to_revoke_for_grantee)

        mock_deletegrants.assert_not_called()
