from __future__ import absolute_import
from datetime import date

from django.apps import apps
from django.db import connection, transaction
from django.db.models import Q

from corehq.apps.accounting.models import Subscription
from corehq.apps.accounting.utils import get_change_status


class BaseDeletion(object):

    def __init__(self, app_label):
        self.app_label = app_label

    def is_app_installed(self):
        try:
            return bool(apps.get_app_config(self.app_label))
        except LookupError:
            return False


class CustomDeletion(BaseDeletion):

    def __init__(self, app_label, deletion_fn):
        super(CustomDeletion, self).__init__(app_label)
        self.deletion_fn = deletion_fn

    def execute(self, domain_name):
        if self.is_app_installed():
            self.deletion_fn(domain_name)


class RawDeletion(BaseDeletion):

    def __init__(self, app_label, raw_query):
        super(RawDeletion, self).__init__(app_label)
        self.raw_query = raw_query

    def execute(self, cursor, domain_name):
        if self.is_app_installed():
            cursor.execute(self.raw_query, [domain_name])


class ModelDeletion(BaseDeletion):

    def __init__(self, app_label, model_name, domain_filter_kwarg):
        super(ModelDeletion, self).__init__(app_label)
        self.domain_filter_kwarg = domain_filter_kwarg
        self.model_name = model_name

    def get_model_class(self):
        return apps.get_model(self.app_label, self.model_name)

    def execute(self, domain_name):
        if not domain_name:
            # The Django orm will properly turn a None domain_name to a
            # IS NULL filter. We don't want to allow deleting records for
            # NULL domain names since they might have special meaning (like
            # in some of the SMS models).
            raise RuntimeError("Expected a valid domain name")
        if self.is_app_installed():
            model = self.get_model_class()
            model.objects.filter(**{self.domain_filter_kwarg: domain_name}).delete()


def _delete_domain_backend_mappings(domain_name):
    model = apps.get_model('sms', 'SQLMobileBackendMapping')
    model.objects.filter(is_global=False, domain=domain_name).delete()


def _delete_domain_backends(domain_name):
    model = apps.get_model('sms', 'SQLMobileBackend')
    model.objects.filter(is_global=False, domain=domain_name).delete()


def _delete_web_user_membership(domain_name):
    from corehq.apps.users.models import WebUser
    active_web_users = WebUser.by_domain(domain_name)
    inactive_web_users = WebUser.by_domain(domain_name, is_active=False)
    for web_user in list(active_web_users) + list(inactive_web_users):
        web_user.delete_domain_membership(domain_name)
        web_user.save()


def _terminate_subscriptions(domain_name):
    today = date.today()

    with transaction.atomic():
        current_subscription = Subscription.get_active_subscription_by_domain(domain_name)

        if current_subscription:
            current_subscription.date_end = today
            current_subscription.is_active = False
            current_subscription.save()

            current_subscription.transfer_credits()

            _, downgraded_privs, upgraded_privs = get_change_status(current_subscription.plan_version, None)
            current_subscription.subscriber.deactivate_subscription(
                downgraded_privileges=downgraded_privs,
                upgraded_privileges=upgraded_privs,
                old_subscription=current_subscription,
                new_subscription=None,
            )

        Subscription.objects.filter(
            Q(date_start__gt=today) | Q(date_start=today, is_active=False),
            subscriber__domain=domain_name,
        ).update(is_hidden_to_ops=True)


# We use raw queries instead of ORM because Django queryset delete needs to
# fetch objects into memory to send signals and handle cascades. It makes deletion very slow
# if we have a millions of rows in stock data tables.
DOMAIN_DELETE_OPERATIONS = [
    RawDeletion('stock', """
        DELETE FROM stock_stocktransaction
        WHERE report_id IN (SELECT id FROM stock_stockreport WHERE domain=%s)
    """),
    RawDeletion('stock', "DELETE FROM stock_stockreport WHERE domain=%s"),
    RawDeletion('stock', """
        DELETE FROM commtrack_stockstate
        WHERE product_id IN (SELECT product_id FROM products_sqlproduct WHERE domain=%s)
    """),
    ModelDeletion('products', 'SQLProduct', 'domain'),
    ModelDeletion('locations', 'SQLLocation', 'domain'),
    ModelDeletion('locations', 'LocationType', 'domain'),
    ModelDeletion('stock', 'DocDomainMapping', 'domain_name'),
    ModelDeletion('domain_migration_flags', 'DomainMigrationProgress', 'domain'),
    ModelDeletion('sms', 'SMS', 'domain'),
    ModelDeletion('sms', 'SQLLastReadMessage', 'domain'),
    ModelDeletion('sms', 'ExpectedCallback', 'domain'),
    ModelDeletion('ivr', 'Call', 'domain'),
    ModelDeletion('sms', 'PhoneNumber', 'domain'),
    ModelDeletion('sms', 'MessagingSubEvent', 'parent__domain'),
    ModelDeletion('sms', 'MessagingEvent', 'domain'),
    ModelDeletion('sms', 'SelfRegistrationInvitation', 'domain'),
    CustomDeletion('sms', _delete_domain_backend_mappings),
    ModelDeletion('sms', 'MobileBackendInvitation', 'domain'),
    CustomDeletion('sms', _delete_domain_backends),
    CustomDeletion('users', _delete_web_user_membership),
    CustomDeletion('accounting', _terminate_subscriptions),
]


def apply_deletion_operations(domain_name, dynamic_operations):
    all_ops = dynamic_operations or []
    all_ops.extend(DOMAIN_DELETE_OPERATIONS)
    raw_ops, model_ops = _split_ops_by_type(all_ops)

    with connection.cursor() as cursor:
        for op in raw_ops:
            op.execute(cursor, domain_name)

    for op in model_ops:
        op.execute(domain_name)


def _split_ops_by_type(ops):
    raw_ops = []
    model_ops = []
    for op in ops:
        if isinstance(op, RawDeletion):
            raw_ops.append(op)
        else:
            model_ops.append(op)
    return raw_ops, model_ops
