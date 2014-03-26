class AccountingError(Exception):
    pass


class LineItemError(Exception):
    pass


class InvoiceError(Exception):
    pass


class CreditLineError(Exception):
    pass


class SubscriptionAdjustmentError(Exception):
    pass


class SubscriptionChangeError(Exception):
    pass


class NewSubscriptionError(Exception):
    pass


class InvoiceEmailThrottledError(Exception):
    pass


