from unittest.mock import Mock

from django.test import SimpleTestCase
from testil import eq

from corehq.apps.registry.utils import RegistryPermissionCheck
from corehq.apps.users.models import WebUser, DomainMembership, Permissions, PermissionInfo
from corehq.util.test_utils import generate_cases


class TestRegistryPermissions(SimpleTestCase):
    pass


@generate_cases([
    (None, False, False, False),
    ((), False, False, False),
    (PermissionInfo.ALLOW_ALL, True, True, True),
    (("test_reg",), False, True, True),
    (("other",), False, True, False),
], TestRegistryPermissions)
def test_manage_registry_permission(self, allow, can_manage_all, can_manage_some, can_manage_specific):
    domain = "domain"
    mock_user = _mock_user(domain, "manage_data_registry", allow)
    checker = RegistryPermissionCheck(domain, mock_user)
    eq(checker.can_manage_all, can_manage_all)
    eq(checker.can_manage_some, can_manage_some)
    eq(checker.can_manage_registry("test_reg"), can_manage_specific)


@generate_cases([
    (None, False),
    ((), False),
    (PermissionInfo.ALLOW_ALL, True),
    (("test_reg",), True),
    (("other",), False, ),
], TestRegistryPermissions)
def test_view_registry_permission(self, allow, can_view_data):
    domain = "domain"
    mock_user = _mock_user(domain, "view_data_registry_contents", allow)
    checker = RegistryPermissionCheck(domain, mock_user)
    eq(checker.can_view_registry_data("test_reg"), can_view_data)


def _mock_user(domain, permission_name, permission_allow):
    membership = DomainMembership(domain=domain)

    permissions = []
    if permission_allow is not None:
        permissions = [PermissionInfo(permission_name, permission_allow)]
    mock_role = Mock(permissions=Permissions.from_permission_list(permissions))
    # prime membership.role memoize cache (avoids DB lookup)
    setattr(membership, '_role_cache', {(): mock_role})

    return WebUser(domain_memberships=[membership])

