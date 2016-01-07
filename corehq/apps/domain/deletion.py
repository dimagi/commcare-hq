from django.apps import apps
from django.core.exceptions import ImproperlyConfigured
from django.db import connection


class BaseDeletion(object):
    def __init__(self, app_label):
        self.app_label = app_label

    def is_app_installed(self):
        try:
            return apps.get_app(self.app_label)
        except ImproperlyConfigured:
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
    ModelDeletion('accounting', 'SubscriptionAdjustment', 'subscription__subscriber__domain'),
    ModelDeletion('accounting', 'BillingRecord', 'invoice__subscription__subscriber__domain'),
    ModelDeletion('accounting', 'CreditAdjustment', 'invoice__subscription__subscriber__domain'),
    ModelDeletion('accounting', 'CreditAdjustment', 'credit_line__subscription__subscriber__domain'),
    ModelDeletion('accounting', 'CreditAdjustment', 'related_credit__subscription__subscriber__domain'),
    ModelDeletion('accounting', 'LineItem', 'invoice__subscription__subscriber__domain'),
    ModelDeletion('accounting', 'CreditLine', 'subscription__subscriber__domain'),
    ModelDeletion('accounting', 'Invoice', 'subscription__subscriber__domain'),
    ModelDeletion('accounting', 'Subscription', 'subscriber__domain'),
    ModelDeletion('accounting', 'Subscriber', 'domain'),
    ModelDeletion('sms', 'SMS', 'domain'),
    ModelDeletion('sms', 'MessagingSubEvent', 'parent__domain'),
    ModelDeletion('sms', 'MessagingEvent', 'domain'),
    ModelDeletion('sms', 'SelfRegistrationInvitation', 'domain'),
    ModelDeletion('sms', 'SQLMobileBackendMapping', 'domain'),
    ModelDeletion('sms', 'MobileBackendInvitation', 'domain'),
    ModelDeletion('sms', 'SQLMobileBackend', 'domain'),
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
