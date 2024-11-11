from unittest.mock import Mock, patch

import pytest
from nose.tools import assert_equal
from unmagic import use

from corehq.apps.users.models import CommCareUser, DomainMembership, WebUser
from corehq.apps.users.tests.util import patch_user_data_db_layer

DOMAIN = 'fixture-test'


def _get_domain(name):
    domain = Mock()
    domain.name = name
    domain.commtrack_enabled = True
    return domain


@patch('casexml.apps.phone.models.Domain.get_by_name', _get_domain)
def test_get_commtrack_location_id():
    user = CommCareUser(domain=DOMAIN, domain_membership=DomainMembership(
        domain=DOMAIN, location_id='1', assigned_location_ids=['1']
    ))
    loc_id = user.to_ota_restore_user(DOMAIN).get_commtrack_location_id()
    assert_equal(loc_id, '1')


@pytest.mark.parametrize("user, expected_type", [
    (WebUser(), 'web'),
    (CommCareUser(domain=DOMAIN), 'commcare'),
])
@use("db")
def test_user_types(user, expected_type):
    with patch_user_data_db_layer():
        user_type = user.to_ota_restore_user(DOMAIN).user_session_data['commcare_user_type']
        assert_equal(user_type, expected_type)
