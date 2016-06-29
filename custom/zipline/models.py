import jsonfield
from datetime import datetime
from django.db import models
from django.utils.translation import ugettext_lazy


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

    # A list of {'code': <code>, 'quantity': <quantity>} dictionaries
    # representing the product code and quantity of the products being ordered
    products_requested = jsonfield.JSONField(default=list)

    # Same format as products_requested; represents products and quantities delivered
    # according to the Zipline delivered status update(s)
    products_delivered = jsonfield.JSONField(default=list)

    # Same format as products_requested; represents products and quantities reported
    # to have been received by the facility
    products_confirmed = jsonfield.JSONField(default=list)

    # The timestamp in CommCareHQ that the order was created
    timestamp = models.DateTimeField()

    # The total number of vehicles that will be used to fulfill the request
    total_vehicles = models.IntegerField(null=True)

    # The total number of attempts made while sending this emergency order
    # to Zipline
    zipline_request_attempts = models.IntegerField(default=0)

    # One of the STATUS_* constants from EmergencyOrderStatusUpdate
    status = models.CharField(max_length=126, default=EmergencyOrderStatusUpdate.STATUS_PENDING)

    # A pointer to the EmergencyOrderStatusUpdate record representing the received status update
    received_status = models.ForeignKey('EmergencyOrderStatusUpdate', on_delete=models.PROTECT)

    # A pointer to the EmergencyOrderStatusUpdate record representing the rejected status update
    rejected_status = models.ForeignKey('EmergencyOrderStatusUpdate', on_delete=models.PROTECT)

    # A pointer to the EmergencyOrderStatusUpdate record representing the approved status update
    approved_status = models.ForeignKey('EmergencyOrderStatusUpdate', on_delete=models.PROTECT)

    # A pointer to the EmergencyOrderStatusUpdate record representing the canceled status update
    canceled_status = models.ForeignKey('EmergencyOrderStatusUpdate', on_delete=models.PROTECT)

    # A pointer to the EmergencyOrderStatusUpdate record representing the dispatched status
    # update for the first vehicle
    dispatched_status = models.ForeignKey('EmergencyOrderStatusUpdate', on_delete=models.PROTECT)

    # A pointer to the EmergencyOrderStatusUpdate record representing the delivered status
    # update for the last vehicle
    delivered_status = models.ForeignKey('EmergencyOrderStatusUpdate', on_delete=models.PROTECT)


class EmergencyOrderStatusUpdate(models.Model):
    STATUS_PENDING = 'PENDING'
    STATUS_RECEIVED = 'RECEIVED'
    STATUS_REJECTED = 'REJECTED'
    STATUS_APPROVED = 'APPROVED'
    STATUS_CANCELED = 'CANCELED'
    STATUS_DISPATCHED = 'DISPATCHED'
    STATUS_DELIVERED = 'DELIVERED'
    STATUS_ERROR = 'ERROR'

    STATUS_CHOICES = (
        (STATUS_PENDING, ugettext_lazy('Pending')),
        (STATUS_RECEIVED, ugettext_lazy('Received')),
        (STATUS_REJECTED, ugettext_lazy('Rejected')),
        (STATUS_APPROVED, ugettext_lazy('Approved')),
        (STATUS_CANCELED, ugettext_lazy('Canceled')),
        (STATUS_DISPATCHED, ugettext_lazy('Dispatched')),
        (STATUS_DELIVERED, ugettext_lazy('Delivered')),
        (STATUS_ERROR, ugettext_lazy('Error')),
    )

    class Meta:
        index_together = [
            ['order_id', 'vehicle_number'],
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

    # The vehicle number that this status update applies to, ranging from 1 to
    # order.total_vehicles; this only applies to statuses that are received on
    # a per-vehicle basis, like STATUS_DISPATCHED and STATUS_DELIVERED
    vehicle_number = models.IntegerField(null=True)

    # The unique id in zipline used to identify the vehicle; only applies when
    # vehicle_number also applies
    vehicle_id = models.CharField(max_length=126, null=True)

    # If status == STATUS_DISPATCHED, this should be the products and quantities
    # this vehicle is carrying for this order; the format of this field matches
    # the format of EmergencyOrder.products_requested
    products = jsonfield.JSONField(default=list)

    @classmethod
    def create_for_order(cls, order_id, status, zipline_timestamp=None,
            vehicle_number=None, vehicle_id=None, additional_text=None):
        """
        Creates an EmergencyOrderStatusUpdate record for the given order.
        :param order_id: the id of the EmergencyOrder
        :param status: one of the STATUS_* constants
        :param zipline_timestamp: the value for zipline_timestamp
        :param vehicle_number: the value for vehicle_number
        :param vehicle_id: the value for vehicle_id
        """
        return cls.objects.create(
            order_id=order_id,
            timestamp=datetime.utcnow(),
            zipline_timestamp=zipline_timestamp,
            status=status,
            vehicle_number=vehicle_number,
            vehicle_id=vehicle_id,
            additional_text=additional_text
        )
