from datetime import datetime
from django.core.exceptions import ValidationError
from django.db import models


class SupplyPointStatusValues(object):
    RECEIVED = "received"
    NOT_RECEIVED = "not_received"
    SUBMITTED = "submitted"
    NOT_SUBMITTED = "not_submitted"
    REMINDER_SENT = "reminder_sent"
    ALERT_SENT = "alert_sent"
    CHOICES = [RECEIVED, NOT_RECEIVED, SUBMITTED,
               NOT_SUBMITTED, REMINDER_SENT, ALERT_SENT]


class SupplyPointStatusTypes(object):
    DELIVERY_FACILITY = "del_fac"
    DELIVERY_DISTRICT = "del_dist"
    R_AND_R_FACILITY = "rr_fac"
    R_AND_R_DISTRICT = "rr_dist"
    SOH_FACILITY = "soh_fac"
    SUPERVISION_FACILITY = "super_fac"
    LOSS_ADJUSTMENT_FACILITY = "la_fac"
    DELINQUENT_DELIVERIES = "del_del"

    CHOICE_MAP = {
        DELIVERY_FACILITY: {SupplyPointStatusValues.REMINDER_SENT: "Waiting Delivery Confirmation",
                            SupplyPointStatusValues.RECEIVED: "Delivery received",
                            SupplyPointStatusValues.NOT_RECEIVED: "Delivery Not Received"},
        DELIVERY_DISTRICT: {SupplyPointStatusValues.REMINDER_SENT: "Waiting Delivery Confirmation",
                           SupplyPointStatusValues.RECEIVED: "Delivery received",
                           SupplyPointStatusValues.NOT_RECEIVED: "Delivery not received"},
        R_AND_R_FACILITY: {SupplyPointStatusValues.REMINDER_SENT: "Waiting R&R sent confirmation",
                           SupplyPointStatusValues.SUBMITTED: "R&R Submitted From Facility to District",
                           SupplyPointStatusValues.NOT_SUBMITTED: "R&R Not Submitted"},
        R_AND_R_DISTRICT: {SupplyPointStatusValues.REMINDER_SENT: "R&R Reminder Sent to District",
                           SupplyPointStatusValues.SUBMITTED: "R&R Submitted from District to MSD"},
        SOH_FACILITY: {SupplyPointStatusValues.REMINDER_SENT: "Stock on hand reminder sent to Facility",
                       SupplyPointStatusValues.SUBMITTED: "Stock on hand Submitted"},
        SUPERVISION_FACILITY: {SupplyPointStatusValues.REMINDER_SENT: "Supervision Reminder Sent",
                               SupplyPointStatusValues.RECEIVED: "Supervision Received",
                               SupplyPointStatusValues.NOT_RECEIVED: "Supervision Not Received"},
        LOSS_ADJUSTMENT_FACILITY: {SupplyPointStatusValues.REMINDER_SENT: "Lost/Adjusted Reminder sent to Facility"},
        DELINQUENT_DELIVERIES: {SupplyPointStatusValues.ALERT_SENT: "Delinquent deliveries summary sent to District"},
    }

    @classmethod
    def get_display_name(cls, type, value):
        return cls.CHOICE_MAP[type][value]

    @classmethod
    def is_legal_combination(cls, type, value):
        return type in cls.CHOICE_MAP and value in cls.CHOICE_MAP[type]


class SupplyPointStatus(models.Model):
    status_type = models.CharField(choices=((k, k) for k in SupplyPointStatusTypes.CHOICE_MAP.keys()),
                                   max_length=50)
    status_value = models.CharField(max_length=50,
                                    choices=((c, c) for c in SupplyPointStatusValues.CHOICES))
    status_date = models.DateTimeField(default=datetime.utcnow)
    supply_point = models.CharField(max_length=100, db_index=True)

    def save(self, *args, **kwargs):
        if not SupplyPointStatusTypes.is_legal_combination(self.status_type, self.status_value):
            raise ValueError("%s and %s is not a legal value combination" % \
                             (self.status_type, self.status_value))
        super(SupplyPointStatus, self).save(*args, **kwargs)

    def __unicode__(self):
        return "%s: %s" % (self.status_type, self.status_value)

    @property
    def name(self):
        return SupplyPointStatusTypes.get_display_name(self.status_type, self.status_value)

    class Meta:
        verbose_name = "Facility Status"
        verbose_name_plural = "Facility Statuses"
        get_latest_by = "status_date"
        ordering = ('-status_date',)


class DeliveryGroupReport(models.Model):
    supply_point = models.CharField(max_length=100, db_index=True)
    quantity = models.IntegerField()
    report_date = models.DateTimeField(auto_now_add=True, default=datetime.now())
    message = models.CharField(max_length=100, db_index=True)
    delivery_group = models.CharField(max_length=1)

    class Meta:
        ordering = ('-report_date',)