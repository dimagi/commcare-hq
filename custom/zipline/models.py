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
    product_info = jsonfield.JSONField(default=list)

    # The timestamp in CommCareHQ that the order was created
    timestamp = models.DateTimeField()

    # The total number of vehicles that will be used to fulfill the request
    total_vehicles = models.IntegerField(null=True)


class EmergencyOrderStatusUpdate(models.Model):
    STATUS_RECEIVED = 'RECEIVED'
    STATUS_REJECTED = 'REJECTED'
    STATUS_APPROVED = 'APPROVED'
    STATUS_CANCELED = 'CANCELED'
    STATUS_DISPATCHED = 'DISPATCHED'
    STATUS_DELIVERED = 'DELIVERED'

    STATUS_CHOICES = (
        (STATUS_RECEIVED, ugettext_lazy('Received')),
        (STATUS_REJECTED, ugettext_lazy('Rejected')),
        (STATUS_APPROVED, ugettext_lazy('Approved')),
        (STATUS_CANCELED, ugettext_lazy('Canceled')),
        (STATUS_DISPATCHED, ugettext_lazy('Dispatched')),
        (STATUS_DELIVERED, ugettext_lazy('Delivered')),
    )

    order = models.ForeignKey('EmergencyOrder')

    # The timestamp in CommCareHQ that the status update was received
    timestamp = models.DateTimeField()

    # The timestamp in Zipline that the status update was sent; this will be
    # blank for statuses that are not received asynchronously from Zipline like
    # STATUS_RECEIVED and STATUS_REJECTED
    zipline_timestamp = models.DateTimeField(null=True)

    status = models.CharField(max_length=126, choices=STATUS_CHOICES)

    # The vehicle number that this status update applies to, ranging from 1 to
    # order.total_vehicles; this only applies to statuses that are received on
    # a per-vehicle basis, like STATUS_DISPATCHED and STATUS_DELIVERED
    vehicle_number = models.IntegerField(null=True)

    # The unique id in zipline used to identify the vehicle; only applies when
    # vehicle_number also applies
    vehicle_id = models.CharField(max_length=126, null=True)

    @classmethod
    def create_for_order(cls, order_id, status, zipline_timestamp=None, vehicle_number=None, vehicle_id=None):
        """
        Creates an EmergencyOrderStatusUpdate record for the given order.
        :param order_id: the id of the EmergencyOrder
        :param status: one of the STATUS_* constants
        :param zipline_timestamp: the value for zipline_timestamp
        :param vehicle_number: the value for vehicle_number
        :param vehicle_id: the value for vehicle_id
        """
        cls.objects.create(
            order_id=order_id,
            timestamp=datetime.utcnow(),
            zipline_timestamp=zipline_timestamp,
            status=status,
            vehicle_number=vehicle_number,
            vehicle_id=vehicle_id
        )
