from decimal import Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils.translation import gettext as _

import stripe

from corehq.apps.accounting.models import (
    BillingAccount,
    CreditLine,
    CustomerInvoice,
    Invoice,
    LastPayment,
    PaymentRecord,
    PreOrPostPay,
    StripePaymentMethod,
)
from corehq.apps.accounting.utils import (
    fmt_dollar_amount,
    log_accounting_error,
    log_accounting_info,
)
from corehq.apps.accounting.utils.stripe import charge_through_stripe
from corehq.const import USER_DATE_FORMAT

stripe.api_key = settings.STRIPE_PRIVATE_KEY


class BaseStripePaymentHandler(object):
    """Handler for paying via Stripe's API
    """
    receipt_email_template = None
    receipt_email_template_plaintext = None

    def __init__(self, payment_method, domain):
        self.payment_method = payment_method
        self.domain = domain
        self.account = BillingAccount.get_account_by_domain(self.domain)

    @property
    def cost_item_name(self):
        """Returns a name for the cost item that's used in the logging messages.
        """
        raise NotImplementedError("you must implement cost_item_name")

    def create_charge(self, amount, card=None, customer=None):
        """Process the HTTPRequest used to make this payment

        returns a dict to be used as the json response for the request.
        """
        raise NotImplementedError("you must implement process_request")

    def get_charge_amount(self, request):
        """Returns a Decimal of the amount to be charged.
        """
        raise NotImplementedError("you must implement get_charge_amount")

    def update_credits(self, payment_record):
        """Updates any relevant Credit lines
        """
        raise NotImplementedError("you must implement update_credits")

    def update_payment_information(self, account):
        account.last_payment_method = LastPayment.CC_ONE_TIME
        account.pre_or_post_pay = PreOrPostPay.POSTPAY
        account.save()

    def process_request(self, request):
        customer = None
        amount = self.get_charge_amount(request)
        card = request.POST.get('stripeToken')
        remove_card = request.POST.get('removeCard')
        is_saved_card = request.POST.get('selectedCardType') == 'saved'
        save_card = request.POST.get('saveCard') and not is_saved_card
        autopay = request.POST.get('autopayCard')
        billing_account = BillingAccount.get_account_by_domain(self.domain)
        generic_error = {
            'error': {
                'message': _(
                    "Something went wrong while processing your payment. "
                    "We're working quickly to resolve the issue. No charges "
                    "were issued. Please try again in a few hours."
                ),
            },
        }
        try:
            with transaction.atomic():
                if remove_card:
                    self.payment_method.remove_card(card)
                    return {'success': True, 'removedCard': card, }
                if save_card:
                    card = self.payment_method.create_card(card, billing_account, self.domain, autopay=autopay)
                if save_card or is_saved_card:
                    customer = self.payment_method.customer

                payment_record = PaymentRecord.create_record(
                    self.payment_method, 'temp', amount
                )
                self.update_credits(payment_record)

                charge = self.create_charge(amount, card=card, customer=customer)

            payment_record.transaction_id = charge.id
            payment_record.save()
            self.update_payment_information(billing_account)
        except stripe.error.CardError as e:
            # card was declined
            return e.json_body
        except (
            stripe.error.AuthenticationError,
            stripe.error.InvalidRequestError,
            stripe.error.APIConnectionError,
            stripe.error.StripeError,
        ) as e:
            log_accounting_error(
                "A payment for %(cost_item)s failed due "
                "to a Stripe %(error_class)s: %(error_msg)s" % {
                    'error_class': e.__class__.__name__,
                    'cost_item': self.cost_item_name,
                    'error_msg': e.json_body['error']
                },
                show_stack_trace=True,
            )
            return generic_error
        except Exception as e:
            log_accounting_error(
                "A payment for %(cost_item)s failed due to: %(error_msg)s" % {
                    'cost_item': self.cost_item_name,
                    'error_msg': e,
                },
                show_stack_trace=True,
            )
            return generic_error

        try:
            self.send_email(payment_record)
        except Exception:
            log_accounting_error(
                "Failed to send out an email receipt for "
                "payment related to PaymentRecord No. %s. "
                "Everything else succeeded."
                % payment_record.id,
                show_stack_trace=True,
            )

        return {
            'success': True,
            'card': card,
            'wasSaved': save_card,
            'changedBalance': amount,
        }

    def get_email_context(self):
        return {
            'invoicing_contact_email': settings.INVOICING_CONTACT_EMAIL,
        }

    def send_email(self, payment_record):
        additional_context = self.get_email_context()
        from corehq.apps.accounting.tasks import send_purchase_receipt
        send_purchase_receipt.delay(
            payment_record.id, self.domain, self.receipt_email_template,
            self.receipt_email_template_plaintext, additional_context
        )


class InvoiceStripePaymentHandler(BaseStripePaymentHandler):
    receipt_email_template = 'accounting/email/invoice_receipt.html'
    receipt_email_template_plaintext = 'accounting/email/invoice_receipt.txt'

    def __init__(self, payment_method, domain, invoice):
        super(InvoiceStripePaymentHandler, self).__init__(payment_method, domain)
        self.invoice = invoice

    @property
    def cost_item_name(self):
        return _("Invoice #%s") % self.invoice.id

    def create_charge(self, amount, card=None, customer=None):
        return charge_through_stripe(
            card=card,
            customer=customer,
            amount_in_dollars=amount,
            currency=settings.DEFAULT_CURRENCY,
            description="Payment for Invoice %s" % self.invoice.invoice_number,
        )

    def get_charge_amount(self, request):
        """Returns a Decimal of the amount to be charged.
        """
        if request.POST['paymentAmount'] == 'full':
            return self.invoice.balance.quantize(Decimal(10) ** -2)
        return Decimal(request.POST['customPaymentAmount'])

    def update_credits(self, payment_record):
        # record the credit to the account
        if self.invoice.is_customer_invoice:
            customer_invoice = self.invoice
            subscription_invoice = None
            account = self.invoice.account
        else:
            customer_invoice = None
            subscription_invoice = self.invoice
            account = self.invoice.subscription.account
        CreditLine.add_credit(
            payment_record.amount,
            account=account,
            payment_record=payment_record,
        )
        CreditLine.add_credit(
            -payment_record.amount,
            account=account,
            invoice=subscription_invoice,
            customer_invoice=customer_invoice
        )
        self.invoice.update_balance()
        self.invoice.save()

    def get_email_context(self):
        context = super(InvoiceStripePaymentHandler, self).get_email_context()
        context.update({
            'balance': fmt_dollar_amount(self.invoice.balance),
            'is_paid': self.invoice.is_paid,
            'date_due': self.invoice.date_due.strftime(USER_DATE_FORMAT) if self.invoice.date_due else 'None',
            'invoice_num': self.invoice.invoice_number,
        })
        return context


class BulkStripePaymentHandler(BaseStripePaymentHandler):
    receipt_email_template = 'accounting/email/bulk_payment_receipt.html'
    receipt_email_template_plaintext = 'accounting/email/bulk_payment_receipt.txt'

    def __init__(self, payment_method, domain):
        super(BulkStripePaymentHandler, self).__init__(payment_method, domain)

    @property
    def cost_item_name(self):
        return _('Bulk Payment for project space %s' % self.domain)

    def create_charge(self, amount, card=None, customer=None):
        return charge_through_stripe(
            card=card,
            customer=customer,
            amount_in_dollars=amount,
            currency=settings.DEFAULT_CURRENCY,
            description=self.cost_item_name,
        )

    @property
    def invoices(self):
        if self.account and self.account.is_customer_billing_account:
            return CustomerInvoice.objects.filter(
                account=self.account,
                is_hidden=False
            )
        else:
            return Invoice.objects.filter(
                subscription__subscriber__domain=self.domain,
                is_hidden=False,
            )

    @property
    def balance(self):
        return sum(invoice.balance for invoice in self.invoices)

    def get_charge_amount(self, request):
        if request.POST['paymentAmount'] == 'full':
            return self.balance
        return Decimal(request.POST['customPaymentAmount'])

    def update_credits(self, payment_record):
        amount = payment_record.amount
        for invoice in self.invoices:
            deduct_amount = min(amount, invoice.balance)
            amount -= deduct_amount
            if deduct_amount > 0:
                if self.account and self.account.is_customer_billing_account:
                    customer_invoice = invoice
                    subscription_invoice = None
                    account = self.account
                else:
                    customer_invoice = None
                    subscription_invoice = invoice
                    account = invoice.subscription.account
                # TODO - refactor duplicated functionality
                CreditLine.add_credit(
                    deduct_amount,
                    account=account,
                    payment_record=payment_record,
                )
                CreditLine.add_credit(
                    -deduct_amount,
                    account=account,
                    invoice=subscription_invoice,
                    customer_invoice=customer_invoice
                )
                invoice.update_balance()
                invoice.save()
        if amount:
            account = BillingAccount.get_or_create_account_by_domain(self.domain)[0]
            CreditLine.add_credit(
                amount, account=account,
                payment_record=payment_record,
            )

    def get_email_context(self):
        context = super(BulkStripePaymentHandler, self).get_email_context()
        context.update({
            'is_paid': all(invoice.is_paid for invoice in self.invoices),
            'domain': self.domain,
            'balance': self.balance,
        })
        return context


class CreditStripePaymentHandler(BaseStripePaymentHandler):
    receipt_email_template = 'accounting/email/credit_receipt.html'
    receipt_email_template_plaintext = 'accounting/email/credit_receipt.txt'

    def __init__(self, payment_method, domain, account, subscription=None, post_data=None):
        super(CreditStripePaymentHandler, self).__init__(payment_method, domain)
        if Decimal(post_data.get('general_credit', 0)) > 0:
            self.general_credits = {
                'type': 'general_credit',
                'amount': Decimal(post_data.get('general_credit', 0))
            }
        else:
            self.general_credits = None
        self.post_data = post_data
        self.account = account
        self.subscription = subscription
        self.credit_lines = []

    @property
    def cost_item_name(self):
        return str(self.subscription)

    def get_charge_amount(self, request):
        return Decimal(request.POST['amount'])

    def create_charge(self, amount, card=None, customer=None):
        return charge_through_stripe(
            card=card,
            customer=customer,
            amount_in_dollars=amount,
            currency=settings.DEFAULT_CURRENCY,
            description="Payment for %s" % self.cost_item_name,
        )

    def update_payment_information(self, account):
        account.last_payment_method = LastPayment.CC_ONE_TIME
        account.pre_or_post_pay = PreOrPostPay.PREPAY
        account.save()

    def update_credits(self, payment_record):
        if self.general_credits:
            amount = self.general_credits['amount']
            if amount >= 0.5:
                self.credit_lines.append(CreditLine.add_credit(
                    amount,
                    account=self.account,
                    subscription=self.subscription,
                    payment_record=payment_record,
                ))


class AutoPayInvoicePaymentHandler(object):

    def pay_autopayable_invoices(self, date_due=Ellipsis, domain=None):
        """
        Pays the full balance of all autopayable invoices on date_due
        Note: we use Ellipsis as the default value for date_due because date_due
        can actually be None in the db.
        """
        autopayable_invoices = Invoice.autopayable_invoices(date_due)
        if domain is not None:
            autopayable_invoices = autopayable_invoices.filter(subscription__subscriber__domain=domain)
        for invoice in autopayable_invoices:
            try:
                self._pay_invoice(invoice)
            except Exception as e:
                log_accounting_error("Error autopaying invoice %d: %s" % (invoice.id, e))

    def _pay_invoice(self, invoice):
        log_accounting_info("[Autopay] Autopaying invoice {}".format(invoice.id))
        amount = invoice.balance.quantize(Decimal(10) ** -2)
        if not amount:
            return

        auto_payer = invoice.subscription.account.auto_pay_user
        payment_method = StripePaymentMethod.objects.get(web_user=auto_payer)
        autopay_card = payment_method.get_autopay_card(invoice.subscription.account)
        if autopay_card is None:
            return

        try:
            log_accounting_info("[Autopay] Attempt to charge autopay invoice {} through Stripe".format(invoice.id))
            transaction_id = payment_method.create_charge(
                autopay_card,
                amount_in_dollars=amount,
                description='Auto-payment for Invoice %s' % invoice.invoice_number,
                idempotency_key=f"{invoice.invoice_number}_{amount}"
            )
        except stripe.error.CardError as e:
            self._handle_card_declined(invoice, e)
        except payment_method.STRIPE_GENERIC_ERROR as e:
            self._handle_card_errors(invoice, e)
        else:
            try:
                payment_record = PaymentRecord.create_record(payment_method, transaction_id, amount)
            except IntegrityError:
                log_accounting_error("[Autopay] Attempt to double charge invoice {}".format(invoice.id))
            else:
                invoice.pay_invoice(payment_record)
                invoice.subscription.account.last_payment_method = LastPayment.CC_AUTO
                invoice.account.save()
                self._send_payment_receipt(invoice, payment_record)

    def _send_payment_receipt(self, invoice, payment_record):
        from corehq.apps.accounting.tasks import send_purchase_receipt
        receipt_email_template = 'accounting/email/invoice_receipt.html'
        receipt_email_template_plaintext = 'accounting/email/invoice_receipt.txt'
        try:
            domain = invoice.subscription.subscriber.domain
            context = {
                'invoicing_contact_email': settings.INVOICING_CONTACT_EMAIL,
                'balance': fmt_dollar_amount(invoice.balance),
                'is_paid': invoice.is_paid,
                'date_due': invoice.date_due.strftime(USER_DATE_FORMAT) if invoice.date_due else 'None',
                'invoice_num': invoice.invoice_number,
            }
            send_purchase_receipt.delay(
                payment_record.id, domain, receipt_email_template, receipt_email_template_plaintext, context,
            )
        except Exception:
            self._handle_email_failure(payment_record.id)

    @staticmethod
    def _handle_card_declined(invoice, e):
        from corehq.apps.accounting.tasks import send_autopay_failed

        # https://stripe.com/docs/api/python#error_handling
        body = e.json_body
        err = body.get('error', {})

        log_accounting_error(
            f"[Autopay] An automatic payment failed for invoice: {invoice.id} ({invoice.get_domain()})"
            "because the card was declined. This invoice will not be automatically paid. "
            "Not necessarily actionable, but be aware that this happened. "
            f"error = {err}"
        )
        send_autopay_failed.delay(invoice.id)

    @staticmethod
    def _handle_card_errors(invoice, error):
        log_accounting_error(
            f"[Autopay] An automatic payment failed for invoice: {invoice.id} ({invoice.get_domain()})"
            f"because the of {error}. This invoice will not be automatically paid."
        )

    @staticmethod
    def _handle_email_failure(payment_record_id):
        log_accounting_error(
            "[Autopay] During an automatic payment, sending a payment receipt failed"
            f" for Payment Record: {payment_record_id}. Everything else succeeded"
        )
