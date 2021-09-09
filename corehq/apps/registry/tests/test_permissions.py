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
    membership = DomainMembership(domain=domain)

    permissions = [PermissionInfo("manage_data_registry", allow)] if allow is not None else []
    mock_role = Mock(permissions=Permissions.from_permission_list(permissions))
    # prime membership.role memoize cache (avoids DB lookup)
    setattr(membership, '_role_cache', {(): mock_role})

    user = WebUser(domain_memberships=[membership])

    checker = RegistryPermissionCheck(domain, user)
    eq(checker.can_manage_all, can_manage_all)
    eq(checker.can_manage_some, can_manage_some)
    eq(checker.can_manage_registry("test_reg"), can_manage_specific)
