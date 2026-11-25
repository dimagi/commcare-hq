from unittest.mock import patch

import pytest

from corehq.apps.app_manager.exceptions import (
    AppEditingError,
    RemoteAppsUnsupported,
)
from corehq.apps.app_manager.models import RemoteApp
from corehq.apps.app_manager.models.applications import _create_app_from_doc


@pytest.mark.parametrize(
    'kwargs',
    [
        {},
        {'is_odk': True},
        {'langs': ['en']},
        {'is_odk': True, 'build_profile_id': 'abc'},
        {'with_media': True, 'build_profile_id': 'abc'},
    ],
)
def test_create_profile_is_unsupported(kwargs):
    with _no_fetching(), pytest.raises(RemoteAppsUnsupported):
        _remote_app().create_profile(**kwargs)


def test_create_all_files_is_unsupported():
    with _no_fetching(), pytest.raises(RemoteAppsUnsupported):
        _remote_app().create_all_files()


def test_unsupported_is_an_app_editing_error():
    # Views and validators already handle AppEditingError
    assert issubclass(RemoteAppsUnsupported, AppEditingError)


@pytest.mark.parametrize('doc_type', ['RemoteApp', 'RemoteApp-Deleted'])
def test_apps_cannot_be_created_from_a_remote_app(doc_type):
    source = _remote_app().to_json()
    source['doc_type'] = doc_type
    with pytest.raises(RemoteAppsUnsupported):
        _create_app_from_doc('other-domain', source)


def _remote_app():
    return RemoteApp(
        domain='test-domain', name='remote', profile_url='file:///etc/passwd'
    )


def _no_fetching():
    return patch(
        'urllib.request.urlopen', side_effect=AssertionError('fetched a URL')
    )
