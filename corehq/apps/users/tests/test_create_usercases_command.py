from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase
from corehq.toggles import NAMESPACE_DOMAIN
from corehq.util.test_utils import generate_cases


class CreateUsercasesCommandCombinationsTests(SimpleTestCase):

    @generate_cases([
        # (domain, has_priv, usercase_enabled, toggle_enabled, expected_sync_calls)
        ('priv_enabled_and_toggle_enabled', True, True, True, 0),  # skipped
        ('priv_enabled_and_toggle_disabled', True, True, False, 2),  # expect web user
        ('priv_disabled_and_toggle_enabled', True, False, True, 3),  # expect commcare user and web user
        ('priv_disabled_and_toggle_disabled', True, False, False, 3),  # expect commcare user and web user
        ('nopriv_enabled_and_toggle_enabled', False, True, True, 0),  # skipped (no priv)
        ('nopriv_enabled_and_toggle_disabled', False, True, False, 0),  # skipped (no priv)
        ('nopriv_disabled_and_toggle_enabled', False, False, True, 0),  # skipped (no priv)
        ('nopriv_disabled_and_toggle_disabled', False, False, False, 0),  # skipped (no priv)
    ])
    @patch('corehq.apps.users.management.commands.create_usercases.sync_usercases_ignore_web_flag')
    @patch('corehq.apps.users.management.commands.create_usercases.USH_USERCASES_FOR_WEB_USERS')
    @patch('corehq.apps.users.management.commands.create_usercases.CouchUser.wrap_correctly')
    @patch('corehq.apps.users.management.commands.create_usercases.get_all_user_rows')
    @patch('corehq.apps.users.management.commands.create_usercases.domain_has_privilege')
    @patch('corehq.apps.users.management.commands.create_usercases.Domain.get_by_name')
    @patch('corehq.apps.users.management.commands.create_usercases.Domain.get_all_names')
    @patch('corehq.apps.users.management.commands.create_usercases.any_migrations_in_progress')
    def test_domain_combinations_sync_counts(
        self, domain, has_priv, usercase_enabled, toggle_enabled, expected_sync_calls,
        mock_any_migrations, mock_all_names, mock_get_by_name, mock_has_priv,
        mock_get_all_user_rows, _mock_wrap, mock_toggle, mock_sync
    ):
        mock_all_names.return_value = [domain]

        mock_any_migrations.return_value = False
        mock_get_by_name.return_value = SimpleNamespace(
            usercase_enabled=usercase_enabled, save=lambda: None
        )
        mock_has_priv.side_effect = lambda _domain, _privilege: has_priv
        mock_toggle.enabled.side_effect = lambda _domain: toggle_enabled

        def _rows_side_effect(domain, include_web_users=True, include_mobile_users=True,
                      include_inactive=True, include_docs=False):
            assert not include_inactive and include_docs
            docs = []
            if domain.startswith('priv_enabled'):
                if include_web_users:
                    docs.extend([{'_id': 'w1'}, {'_id': 'w2'}])
                if include_mobile_users:
                    docs.extend([{'_id': 'm1'}])
            elif domain.startswith('priv_disabled'):
                if include_web_users:
                    docs.extend([{'_id': 'w1'}])
                if include_mobile_users:
                    docs.extend([{'_id': 'm1'}, {'_id': 'm2'}])

            for d in docs:
                yield {'doc': d}

        mock_get_all_user_rows.side_effect = _rows_side_effect

        call_command('create_usercases')

        assert mock_sync.call_count == expected_sync_calls

        if expected_sync_calls > 0:
            mock_toggle.set.assert_called_with(domain, True, NAMESPACE_DOMAIN)
        else:
            assert not mock_toggle.set.called
