from unittest.mock import patch

from corehq.apps.accounting.models import Subscription, SubscriptionType
from corehq.apps.groups.models import Group

from ..views import NotificationsServiceRMIView


def test_should_hide_feature_notifs_for_pro_with_groups():
    with case_sharing_groups_patch(['agroupid']):
        hide = NotificationsServiceRMIView._should_hide_feature_notifs("test", "pro")
        assert hide, "notifications should be hidden for pro domain with groups"


def test_should_hide_feature_notifs_for_pro_without_groups():
    with case_sharing_groups_patch([]), active_service_type_patch(TRIAL):
        hide = NotificationsServiceRMIView._should_hide_feature_notifs("test", "pro")
        assert not hide, "notifications should not be hidden for pro domain without groups"


def test_should_hide_feature_notifs_for_implementation_subscription():
    with active_service_type_patch(IMPLEMENTATION):
        hide = NotificationsServiceRMIView._should_hide_feature_notifs("test", "basic")
        assert hide, f"notifications should be hidden for {IMPLEMENTATION} subscription"


def test_should_hide_feature_notifs_for_sandbox_subscription():
    with active_service_type_patch(SANDBOX):
        hide = NotificationsServiceRMIView._should_hide_feature_notifs("test", "basic")
        assert hide, f"notifications should be hidden for {SANDBOX} subscription"


def test_should_hide_feature_notifs_bug():
    with active_service_type_patch():
        hide = NotificationsServiceRMIView._should_hide_feature_notifs("test", "basic")
        assert not hide, "notifications should not be hidden for null subscription"


def active_service_type_patch(service_type=None):
    def getter(domain):
        return sub
    sub = None if service_type is None else Subscription(service_type=service_type)
    return patch.object(Subscription, "get_active_subscription_by_domain", getter)


def case_sharing_groups_patch(groups):
    # patch because quickcache makes this hard to test
    def getter(domain, wrap):
        assert not wrap, "expected wrap to be false"
        return groups
    return patch.object(Group, "get_case_sharing_groups", getter)


IMPLEMENTATION = SubscriptionType.IMPLEMENTATION
SANDBOX = SubscriptionType.SANDBOX
TRIAL = SubscriptionType.TRIAL
