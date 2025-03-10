import pytest
from unittest.mock import patch
from corehq.apps.app_manager.management.commands.helpers import AppMigrationCommandBase


@pytest.mark.django_db
def test_migrate_app():
    # Create a mock instance of AppMigrationCommandBase
    command = AppMigrationCommandBase()
    command.DOMAIN_LIST_FILENAME = "DOMAIN_LIST_FILENAME"
    command.DOMAIN_PROGRESS_NUMBER_FILENAME = "DOMAIN_PROGRESS_NUMBER_FILENAME"

    with patch('corehq.apps.app_manager.management.commands.helpers.iter_update') as mock_iter_update:
        with patch.object(command, 'get_app_ids', return_value={'test_app_id'}):
            command.handle(
                domain=None,
                start_from_scratch=False,
                dry_run=False,
                failfast=False,
            )
        mock_iter_update.assert_called_once()
