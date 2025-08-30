from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase


class CreateUsercasesCommandCombinationsTests(SimpleTestCase):

    @patch('corehq.apps.users.management.commands.create_usercases.sync_usercases_ignore_web_flag')
    @patch('corehq.apps.users.management.commands.create_usercases.CommCareUser.by_domain')
    @patch('corehq.apps.users.management.commands.create_usercases.WebUser.by_domain')
    @patch('corehq.apps.users.management.commands.create_usercases.domain_has_privilege')
    @patch('corehq.apps.users.management.commands.create_usercases.Domain.get_by_name')
    @patch('corehq.apps.users.management.commands.create_usercases.Domain.get_all_names')
    def test_domain_combinations_enqueue_and_counts(
        self, mock_all_names, mock_get_by_name, mock_has_priv, mock_web_by_domain, mock_cc_by_domain, mock_sync
    ):
        # Define domains with combinations of (has_privilege, usercase_enabled)
        combos = {
            'priv_enabled': (True, True),   # expect only web user
            'priv_disabled': (True, False),  # expect commcare user and web user
            'nopriv_enabled': (False, True),  # expect skip
            'nopriv_disabled': (False, False),  # expect skip
        }
        mock_all_names.return_value = list(combos.keys())

        def _get_by_name(name):
            _, usercase_enabled = combos[name]
            return SimpleNamespace(usercase_enabled=usercase_enabled,
                                   save=lambda: None)

        def _has_priv(name, *_):
            has_priv, _ = combos[name]
            return has_priv

        def _web_users(domain):
            if domain == 'priv_enabled':
                return [SimpleNamespace(), SimpleNamespace()]
            if domain == 'priv_disabled':
                return [SimpleNamespace()]
            return []

        def _cc_users(domain):
            if domain == 'priv_disabled':
                return [SimpleNamespace(), SimpleNamespace()]
            return []

        mock_get_by_name.side_effect = _get_by_name
        mock_has_priv.side_effect = _has_priv
        mock_web_by_domain.side_effect = _web_users
        mock_cc_by_domain.side_effect = _cc_users

        call_command('create_usercases')

        # 2 web (priv_enabled) + 1 web (priv_disabled) + 2 commcare (priv_disabled) = 5
        assert mock_sync.call_count == 5

        called_domains = {c.args[1] for c in mock_sync.call_args_list}
        assert called_domains == {'priv_enabled', 'priv_disabled'}
