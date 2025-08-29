from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase


class CreateUsercasesCommandCombinationsTests(SimpleTestCase):

    @patch('corehq.apps.users.management.commands.create_usercases.create_usercases_for_user_type.delay')
    @patch('corehq.apps.users.management.commands.create_usercases.domain_has_privilege')
    @patch('corehq.apps.users.management.commands.create_usercases.Domain.get_by_name')
    @patch('corehq.apps.users.management.commands.create_usercases.Domain.get_all_names')
    def test_domain_combinations_enqueue_and_counts(
        self, mock_all_names, mock_get_by_name, mock_has_priv, mock_delay
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
            return SimpleNamespace(usercase_enabled=usercase_enabled)

        def _has_priv(name, *_):
            has_priv, _ = combos[name]
            return has_priv

        mock_get_by_name.side_effect = _get_by_name
        mock_has_priv.side_effect = _has_priv

        call_command('create_usercases')

        mock_delay.assert_any_call('priv_enabled', include_web_users=True)
        mock_delay.assert_any_call('priv_disabled', include_commcare_users=True, include_web_users=True)

        assert mock_delay.call_count == 2

        called_domains = {c.args[0] for c in mock_delay.call_args_list}
        assert 'nopriv_enabled' not in called_domains
        assert 'nopriv_disabled' not in called_domains
