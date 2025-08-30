from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase


class CreateUsercasesCommandCombinationsTests(SimpleTestCase):

    @patch('corehq.apps.users.management.commands.create_usercases.sync_usercases_ignore_web_flag')
    @patch('corehq.apps.users.management.commands.create_usercases.USH_USERCASES_FOR_WEB_USERS')
    @patch('corehq.apps.users.management.commands.create_usercases.CommCareUser.by_domain')
    @patch('corehq.apps.users.management.commands.create_usercases.WebUser.by_domain')
    @patch('corehq.apps.users.management.commands.create_usercases.domain_has_privilege')
    @patch('corehq.apps.users.management.commands.create_usercases.Domain.get_by_name')
    @patch('corehq.apps.users.management.commands.create_usercases.Domain.get_all_names')
    def test_domain_combinations_enqueue_and_counts(
        self, mock_all_names, mock_get_by_name, mock_has_priv,
        mock_web_by_domain, mock_cc_by_domain, mock_toggle, mock_sync
    ):
        # Define domains with combinations of (has_privilege, usercase_enabled, usercase_toggle_enabled)
        combos = {
            'priv_enabled_and_toggle_enabled': (True, True, True),  # expect skip
            'priv_enabled_and_toggle_disabled': (True, True, False),  # expect only web user
            'priv_disabled_and_toggle_enabled': (True, False, True),  # expect commcare user and web user
            'priv_disabled_and_toggle_disabled': (True, False, False),  # expect commcare user and web user
            'nopriv_enabled_and_toggle_enabled': (False, True, True),  # expect skip
            'nopriv_enabled_and_toggle_disabled': (False, True, False),  # expect skip
            'nopriv_disabled_and_toggle_enabled': (False, False, True),  # expect skip
            'nopriv_disabled_and_toggle_disabled': (False, False, False),  # expect skip
        }
        mock_all_names.return_value = list(combos.keys())

        def _get_by_name(name):
            _, usercase_enabled, _ = combos[name]
            return SimpleNamespace(usercase_enabled=usercase_enabled,
                                   save=lambda: None)

        def _has_priv(name, *_):
            has_priv, _, _ = combos[name]
            return has_priv

        mock_toggle.enabled.side_effect = lambda domain: combos[domain][2]

        def _web_users(domain):
            if domain.startswith('priv_enabled'):
                return [SimpleNamespace(), SimpleNamespace()]
            if domain.startswith('priv_disabled'):
                return [SimpleNamespace()]
            return []

        def _cc_users(domain):
            if domain.startswith('priv_disabled'):
                return [SimpleNamespace(), SimpleNamespace()]
            return []

        mock_get_by_name.side_effect = _get_by_name
        mock_has_priv.side_effect = _has_priv
        mock_web_by_domain.side_effect = _web_users
        mock_cc_by_domain.side_effect = _cc_users

        call_command('create_usercases')

        # Processed domains:
        # - priv_enabled_and_toggle_disabled: 2 web
        # - priv_disabled_and_toggle_enabled: 1 web + 2 commcare
        # - priv_disabled_and_toggle_disabled: 1 web + 2 commcare
        # Total sync calls = 2 + 3 + 3 = 8
        assert mock_sync.call_count == 8

        called_domains = {c.args[1] for c in mock_sync.call_args_list}
        assert called_domains == {
            'priv_enabled_and_toggle_disabled',
            'priv_disabled_and_toggle_enabled',
            'priv_disabled_and_toggle_disabled',
        }

        # Flag set only for processed domains
        set_domains = {c.args[0] for c in mock_toggle.set.call_args_list}
        assert set_domains == {
            'priv_enabled_and_toggle_disabled',
            'priv_disabled_and_toggle_enabled',
            'priv_disabled_and_toggle_disabled',
        }
