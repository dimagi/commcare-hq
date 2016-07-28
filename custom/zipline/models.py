import jsonfield
from datetime import datetime
from decimal import Decimal
from django.db import models


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

    class Meta:
        index_together = [
            ['order', 'package_number'],
        ]

    order = models.ForeignKey('EmergencyOrder')

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
        index_together = [
            ['order', 'package_number'],
        ]

        unique_together = [
            ['order', 'package_number'],
        ]

    # (order, package_number) matches up with the same-named fields on EmergencyOrderStatusUpdate
    order = models.ForeignKey('EmergencyOrder')
    package_number = models.IntegerField()

    # Same format as EmergencyOrder.products_requested; represents products and quantities
    # in this package
    products = jsonfield.JSONField(default=dict)

    # Should either be STATUS_DISPATCHED, STATUS_DELIVERED, or STATUS_CANCELLED_IN_FLIGHT
    status = models.CharField(max_length=126)

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
