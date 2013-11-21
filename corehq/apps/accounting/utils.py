

class BaseChoice(object):

    @classmethod
    def get_choices(cls):
        """
        Returns a list of choices:
        [
            (<value>, <user text>),
        ]
        """
        raise NotImplementedError("please return a list of choices")


class BillingAccountType(BaseChoice):
    CONTRACT = "CONTRACT"
    USER_CREATED = "USER_CREATED"

    @classmethod
    def get_choices(cls):
        return (
            (cls.CONTRACT, "Created by contract"),
            (cls.USER_CREATED, "Created by user"),
        )


class AdjustmentReason(BaseChoice):
    DIRECT_PAYMENT = "DIRECT_PAYMENT"
    SALESFORCE = "SALESFORCE"
    INVOICE = "INVOICE"
    MANUAL = "MANUAL"

    @classmethod
    def get_choices(cls):
        return (
            (cls.MANUAL, "manual"),
            (cls.SALESFORCE, "via Salesforce"),
            (cls.INVOICE, "invoice generated"),
            (cls.DIRECT_PAYMENT, "payment from client received"),
        )


class SubscriptionAdjustmentReason(BaseChoice):
    CREATE = "CREATE"
    MODIFY = "MODIFY"
    CANCEL = "CANCEL"

    @classmethod
    def get_choices(cls):
        return (
            (cls.CREATE, "Subscription created"),
            (cls.MODIFY, "Subscription modified"),
            (cls.CANCEL, "Subscription was cancelled"),
        )


class SoftwarePlanVisibility(BaseChoice):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"

    @classmethod
    def get_choices(cls):
        return (
            (cls.PUBLIC, "Anyone can subscribe"),
            (cls.INTERNAL, "Dimagi must create subscription"),
        )
