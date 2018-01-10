from __future__ import absolute_import
from django.utils.translation import ugettext_lazy as _

import jsonfield
from datetime import datetime
from decimal import Decimal, InvalidOperation
from django.db import models
import six


class EmergencyOrderStatusUpdate(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_ERROR = 'error'
    STATUS_RECEIVED = 'received'
    STATUS_REJECTED = 'rejected'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_CANCELLED_BY_USER = 'cancelledByUser'

    # The following statuses match the values received from zipline via our
    # API. Do not change these constants otherwise the API will not work properly.
    STATUS_APPROVED = 'approved'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CANCELLED_IN_FLIGHT = 'cancelledInFlight'
    STATUS_DISPATCHED = 'dispatched'
    STATUS_APPROACHING_ETA = 'approachingEta'
    STATUS_ETA_DELAYED = 'etaDelayed'
    STATUS_DELIVERED = 'delivered'

    STATUS_CHOICES = (
        (STATUS_PENDING, _('Pending')),
        (STATUS_ERROR, _('Error')),
        (STATUS_RECEIVED, _('Received')),
        (STATUS_REJECTED, _('Rejected')),
        (STATUS_CONFIRMED, _('Confirmed')),
        (STATUS_CANCELLED_BY_USER, _('Cancelled by user')),
        (STATUS_APPROVED, _('Approved')),
        (STATUS_CANCELLED, _('Cancelled')),
        (STATUS_CANCELLED_IN_FLIGHT, _('Cancelled in Flight')),
        (STATUS_DISPATCHED, _('Dispatched')),
        (STATUS_APPROACHING_ETA, _('Approaching Eta')),
        (STATUS_ETA_DELAYED, _('Eta delayed')),
        (STATUS_DELIVERED, _('Delivered'))
    )

    class Meta:
        app_label = 'zipline'
        index_together = [
            ['order', 'package_number'],
        ]

    order = models.ForeignKey('EmergencyOrder', on_delete=models.CASCADE)

    # The timestamp in CommCareHQ that the status update was received
    timestamp = models.DateTimeField()

    # The timestamp in Zipline that the status update was sent; this will be
    # blank for statuses that are not received asynchronously from Zipline like
    # STATUS_RECEIVED and STATUS_REJECTED
    zipline_timestamp = models.DateTimeField(null=True)

    # One of the STATUS_* constants above
    status = models.CharField(max_length=126)

    # Optionally, some additional information about the status, such as an
    # error code or error message
    additional_text = models.TextField(null=True)

    # The package number that this status update applies to, ranging from 1 to
    # order.total_packages; this only applies to statuses that are received on
    # a per-vehicle basis, like STATUS_DISPATCHED and STATUS_DELIVERED
    package_number = models.IntegerField(null=True)

    # The unique id zipline uses to identify the package
    package_id = models.CharField(max_length=126, null=True)

    # The unique id zipline uses to identify the vehicle
    vehicle_id = models.CharField(max_length=126, null=True)

    # If status == STATUS_DISPATCHED, this should be the products and quantities
    # this vehicle is carrying for this order; the format of this field matches
    # the format of EmergencyOrder.products_requested
    products = jsonfield.JSONField(default=dict)

    # If status == STATUS_DISPATCHED or STATUS_ETA_DELAYED, this will be the eta of
    # this package's delivery, in UTC
    eta = models.TimeField(null=True)

    # If status == STATUS_APPROACHING_ETA, this will be the minutes left until the
    # package will be delivered
    eta_minutes_remaining = models.IntegerField(null=True)

    @classmethod
    def create_for_order(cls, order_id, status, zipline_timestamp=None,
            package_number=None, package_id=None, vehicle_id=None, additional_text=None,
            products=None, eta=None, eta_minutes_remaining=None):
        """
        Creates an EmergencyOrderStatusUpdate record for the given order.
        :param order_id: the id of the EmergencyOrder
        :param status: one of the STATUS_* constants
        :param zipline_timestamp: the value for zipline_timestamp
        :param package_number: the value for package_number
        :param package_id: the value for package_id
        :param vehicle_id: the value for vehicle_id
        :param additional_text: the value for additional_text
        :param products: a list of ProductQuantity objects if this status
        update is associated with products
        """
        obj = cls(
            order_id=order_id,
            timestamp=datetime.utcnow(),
            zipline_timestamp=zipline_timestamp,
            status=status,
            package_number=package_number,
            package_id=package_id,
            vehicle_id=vehicle_id,
            additional_text=additional_text,
            eta=eta,
            eta_minutes_remaining=eta_minutes_remaining
        )

        if products:
            update_product_quantity_json_field(obj.products, products)

        obj.save()
        return obj


class EmergencyOrder(models.Model):

    class Meta:
        app_label = 'zipline'

    domain = models.CharField(max_length=126)

    # The id of the user who initiated the order
    requesting_user_id = models.CharField(max_length=126)

    # The phone number from which the order was initiated
    requesting_phone_number = models.CharField(max_length=126)

    # The location to which the order should be delivered
    location = models.ForeignKey('locations.SQLLocation', on_delete=models.PROTECT)

    # The location code of the location, stored here redundantly so that we
    # can always see historically what it was at the time of the request
    location_code = models.CharField(max_length=126)

    # A dictionary of {'code': <product info>, ...} where each key is a product
    # code and each value is a dictionary with information about the product;
    # <product info> has the structure: {'quantity': <quantity>}
    products_requested = jsonfield.JSONField(default=dict)

    # Same format as products_requested; represents products and quantities delivered
    # according to the Zipline delivered status update(s)
    products_delivered = jsonfield.JSONField(default=dict)

    # Same format as products_requested; represents products and quantities reported
    # to have been received by the facility
    products_confirmed = jsonfield.JSONField(default=dict)

    # The timestamp in CommCareHQ that the order was created
    timestamp = models.DateTimeField()

    # The total number of packages that will be used to fulfill the request
    total_packages = models.IntegerField(null=True)

    # The total number of attempts made while sending this emergency order to Zipline
    zipline_request_attempts = models.IntegerField(default=0)

    # One of the STATUS_* constants from EmergencyOrderStatusUpdate
    status = models.CharField(max_length=126, default=EmergencyOrderStatusUpdate.STATUS_PENDING)

    # A pointer to the EmergencyOrderStatusUpdate record representing the received status update
    received_status = models.ForeignKey('EmergencyOrderStatusUpdate', on_delete=models.PROTECT,
        related_name='+', null=True)

    # A pointer to the EmergencyOrderStatusUpdate record representing the rejected status update
    rejected_status = models.ForeignKey('EmergencyOrderStatusUpdate', on_delete=models.PROTECT,
        related_name='+', null=True)

    # A pointer to the EmergencyOrderStatusUpdate record representing the approved status update
    approved_status = models.ForeignKey('EmergencyOrderStatusUpdate', on_delete=models.PROTECT,
        related_name='+', null=True)

    # A pointer to the EmergencyOrderStatusUpdate record representing the cancelled status update
    # This might also point to a cancelled in flight status update in the event that the order was
    # dispatched and then all filghts were cancelled.
    cancelled_status = models.ForeignKey('EmergencyOrderStatusUpdate', on_delete=models.PROTECT,
        related_name='+', null=True)

    # A pointer to the EmergencyOrderStatusUpdate record representing the dispatched status
    # update for the first vehicle
    dispatched_status = models.ForeignKey('EmergencyOrderStatusUpdate', on_delete=models.PROTECT,
        related_name='+', null=True)

    # A pointer to the EmergencyOrderStatusUpdate record representing the delivered status
    # update for the last vehicle
    delivered_status = models.ForeignKey('EmergencyOrderStatusUpdate', on_delete=models.PROTECT,
        related_name='+', null=True)

    # A pointer to the EmergencyOrderStatusUpdate record representing the first receipt
    # confirmation received
    confirmed_status = models.ForeignKey('EmergencyOrderStatusUpdate', on_delete=models.PROTECT,
        related_name='+', null=True)


class EmergencyOrderPackage(models.Model):

    class Meta:
        app_label = 'zipline'

        index_together = [
            ['order', 'package_number'],
        ]

        unique_together = [
            ['order', 'package_number'],
        ]

    # (order, package_number) matches up with the same-named fields on EmergencyOrderStatusUpdate
    order = models.ForeignKey('EmergencyOrder', on_delete=models.CASCADE)
    package_number = models.IntegerField()

    # Same format as EmergencyOrder.products_requested; represents products and quantities
    # in this package
    products = jsonfield.JSONField(default=dict)

    # Should either be STATUS_DISPATCHED, STATUS_DELIVERED, or STATUS_CANCELLED_IN_FLIGHT
    status = models.CharField(max_length=126, default=EmergencyOrderStatusUpdate.STATUS_DISPATCHED)

    # A pointer to the EmergencyOrderStatusUpdate representing the dispatched status update
    # for this package
    dispatched_status = models.ForeignKey('EmergencyOrderStatusUpdate', on_delete=models.PROTECT,
        related_name='+', null=True)

    # A pointer to the EmergencyOrderStatusUpdate representing the delivered status update
    # for this package
    delivered_status = models.ForeignKey('EmergencyOrderStatusUpdate', on_delete=models.PROTECT,
        related_name='+', null=True)

    # A pointer to the EmergencyOrderStatusUpdate representing the cancelled in flight status update
    # for this package
    cancelled_status = models.ForeignKey('EmergencyOrderStatusUpdate', on_delete=models.PROTECT,
        related_name='+', null=True)

    # The total cost of all products in this package, using info from OrderableProduct
    cost = models.DecimalField(max_digits=12, decimal_places=3, null=True)

    # The total weight of this package in grams, using info from OrderableProduct
    weight = models.DecimalField(max_digits=12, decimal_places=3, null=True)

    def update_calculated_fields(self):
        """
        Updates the cost and the weight of the package.
        Note that this uses the active record for the product, so this method
        should only be called in real-time (not on historical data).
        """
        from custom.zipline.api import log_zipline_exception

        cost = Decimal(0)
        weight = Decimal(0)

        for code, data in six.iteritems(self.products):
            try:
                product = OrderableProduct.objects.get(domain=self.order.domain, code=code)
            except OrderableProduct.DoesNotExist:
                log_zipline_exception(
                    "Failed to update calculated fields - product not found",
                    details={
                        'EmergencyOrderPackage_pk': self.pk,
                        'product_code': code,
                    }
                )
                continue

            try:
                quantity = Decimal(data['quantity'])
            except (KeyError, TypeError, InvalidOperation):
                log_zipline_exception(
                    "Failed to update calculated fields - invalid quantity",
                    details={
                        'EmergencyOrderPackage_pk': self.pk,
                        'product_code': code,
                    }
                )
                continue

            cost += product.cost * quantity
            weight += product.weight * quantity

        self.cost = cost
        self.weight = weight


class BaseOrderableProduct(models.Model):

    class Meta:
        abstract = True
        app_label = 'zipline'
        unique_together = [
            ['domain', 'code'],
        ]

    # The domain that this product applies to
    domain = models.CharField(max_length=126)

    # The product code that is used in the order requests
    code = models.CharField(max_length=126)

    # The name of the product
    name = models.CharField(max_length=126)

    # A short description of the product, small enough to fit in an SMS but descriptive enough
    # to understand what it is
    description = models.CharField(max_length=126)

    # The cost of 1 unit of this product (for now always in TZS)
    cost = models.DecimalField(max_digits=12, decimal_places=3)

    # A description of the size of 1 unit of this product
    unit_description = models.CharField(max_length=126)

    # The weight, in grams, of 1 unit of this product
    weight = models.DecimalField(max_digits=12, decimal_places=3)

    # The maximum number of units allowed to be ordered in a single order
    max_units_allowed = models.IntegerField()


class OrderableProduct(BaseOrderableProduct):
    """
    Each entry in this table represents a product that is currently orderable
    through Zipline for the given domain. If a product is no longer currently
    orderable, it should be removed from this table.

    To see what products were available at what time, the OrderableProductHistory
    model can be used.
    """
    pass


class OrderableProductHistory(BaseOrderableProduct):
    """
    This models keeps track of changes to the OrderableProduct table by showing
    what products were available at a given point in time.

    It's expected that each code should not have more than one record in this table
    with overlapping effective start and end timestamps.

    The effective start and end timestamps are used to:

    1) Keep track of which products were available for ordering at what point in history.
       When a product is made unavailable for ordering, it's effective end timestamp should
       be updated to be the current date and time.

    2) Keep track of the information associated with the product over the given time
       period. So for example, if the price of a unit of a product changes, a new
       record should be inserted for the product with an effective start timestamp of
       the current date and time.
    """

    # The date and time that this product started being available for orders.
    effective_start_timestamp = models.DateTimeField()

    # The date and time that this product stopped being available for orders.
    # This should not be null. For active products set it to 9999-12-31.
    effective_end_timestamp = models.DateTimeField()


def update_product_quantity_json_field(json_field, products):
    """
    Updates the product quantities stored in the given field.
    If the products are already present, the quantity is added to the current
    quantity for that product.
    :param json_field: the dictionary that should be updated (for example,
    order.products_delivered)
    :param products: a list of ProductQuantity objects representing the products
    and quantities to update
    """
    for product in products:
        if product.code not in json_field:
            json_field[product.code] = {'quantity': '0'}

        product_info = json_field[product.code]
        current_value = Decimal(product_info['quantity'])
        new_value = current_value + Decimal(product.quantity)
        product_info['quantity'] = '{0:f}'.format(new_value)
