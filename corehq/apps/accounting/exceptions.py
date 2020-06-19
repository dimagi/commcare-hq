class AccountingError(Exception):
    pass


class LineItemError(Exception):
    pass


class InvoiceError(Exception):
    pass


class InvoiceAlreadyCreatedError(Exception):
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


class SubscriptionReminderError(Exception):
    pass


class SubscriptionRenewalError(Exception):
    pass


class PaymentRequestError(Exception):
    pass


class PaymentHandlerError(Exception):
    pass


class CreateAccountingAdminError(Exception):
    pass


class ProductPlanNotFoundError(Exception):
    pass


class EnterpriseReportError(Exception):
    pass


class NoActiveSubscriptionError(Exception):
    pass


class MultipleActiveSubscriptionsError(Exception):
    pass


class ActiveSubscriptionWithoutDomain(Exception):
    pass


class CreditLineBalanceMismatchError(Exception):
    pass


class AccountingCommunicationError(Exception):
    pass


class SubscriptionTaskError(Exception):
    pass
