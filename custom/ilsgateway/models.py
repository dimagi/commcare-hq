from datetime import datetime

from couchdbkit.ext.django.schema import Document, BooleanProperty, StringProperty
from django.db import models

from casexml.apps.stock.models import DocDomainMapping
from corehq.apps.products.models import Product
from corehq.apps.locations.models import SQLLocation
from dimagi.utils.dates import force_to_datetime


class ILSGatewayConfig(Document):
    enabled = BooleanProperty(default=False)
    domain = StringProperty()
    url = StringProperty(default="http://ilsgateway.com/api/v0_1")
    username = StringProperty()
    password = StringProperty()
    steady_sync = BooleanProperty(default=False)
    all_stock_data = BooleanProperty(default=False)

    @classmethod
    def for_domain(cls, name):
        try:
            mapping = DocDomainMapping.objects.get(domain_name=name, doc_type='ILSGatewayConfig')
            return cls.get(docid=mapping.doc_id)
        except DocDomainMapping.DoesNotExist:
            return None

    @classmethod
    def get_all_configs(cls):
        mappings = DocDomainMapping.objects.filter(doc_type='ILSGatewayConfig')
        configs = [cls.get(docid=mapping.doc_id) for mapping in mappings]
        return configs

    @classmethod
    def get_all_enabled_domains(cls):
        configs = cls.get_all_configs()
        return [c.domain for c in filter(lambda config: config.enabled, configs)]

    @classmethod
    def get_all_steady_sync_configs(cls):
        return [
            config for config in cls.get_all_configs()
            if config.steady_sync
        ]

    @property
    def is_configured(self):
        return True if self.enabled and self.url and self.password and self.username else False

    def save(self, **params):
        super(ILSGatewayConfig, self).save(**params)
        try:
            DocDomainMapping.objects.get(doc_id=self._id,
                                         domain_name=self.domain,
                                         doc_type="ILSGatewayConfig")
        except DocDomainMapping.DoesNotExist:
            DocDomainMapping.objects.create(doc_id=self._id,
                                            domain_name=self.domain,
                                            doc_type='ILSGatewayConfig')


# Ported from:
# https://github.com/dimagi/logistics/blob/tz-master/logistics_project/apps/tanzania/models.py#L68
class SupplyPointStatusValues(object):
    RECEIVED = "received"
    NOT_RECEIVED = "not_received"
    SUBMITTED = "submitted"
    NOT_SUBMITTED = "not_submitted"
    REMINDER_SENT = "reminder_sent"
    ALERT_SENT = "alert_sent"
    CHOICES = [RECEIVED, NOT_RECEIVED, SUBMITTED,
               NOT_SUBMITTED, REMINDER_SENT, ALERT_SENT]


# Ported from:
# https://github.com/dimagi/logistics/blob/tz-master/logistics_project/apps/tanzania/models.py#L78
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
        LOSS_ADJUSTMENT_FACILITY: {
            SupplyPointStatusValues.REMINDER_SENT: "Lost/Adjusted Reminder sent to Facility"
        },
        DELINQUENT_DELIVERIES: {
            SupplyPointStatusValues.ALERT_SENT: "Delinquent deliveries summary sent to District"
        },
    }

    @classmethod
    def get_display_name(cls, type, value):
        return cls.CHOICE_MAP[type][value]

    @classmethod
    def is_legal_combination(cls, type, value):
        return type in cls.CHOICE_MAP and value in cls.CHOICE_MAP[type]


# Ported from: https://github.com/dimagi/logistics/blob/tz-master/logistics_project/apps/tanzania/models.py#L124
class SupplyPointStatus(models.Model):
    status_type = models.CharField(choices=((k, k) for k in SupplyPointStatusTypes.CHOICE_MAP.keys()),
                                   max_length=50)
    status_value = models.CharField(max_length=50,
                                    choices=((c, c) for c in SupplyPointStatusValues.CHOICES))
    status_date = models.DateTimeField(default=datetime.utcnow)
    supply_point = models.CharField(max_length=100, db_index=True)
    external_id = models.PositiveIntegerField(null=True, db_index=True)

    def save(self, *args, **kwargs):
        if not SupplyPointStatusTypes.is_legal_combination(self.status_type, self.status_value):
            raise ValueError("%s and %s is not a legal value combination" %
                             (self.status_type, self.status_value))
        super(SupplyPointStatus, self).save(*args, **kwargs)

    def __unicode__(self):
        return "%s: %s" % (self.status_type, self.status_value)

    @property
    def name(self):
        return SupplyPointStatusTypes.get_display_name(self.status_type, self.status_value)

    @classmethod
    def wrap_from_json(cls, obj, location_id):
        obj['supply_point'] = location_id
        obj['external_id'] = obj['id']
        del obj['id']
        return cls(**obj)

    class Meta:
        verbose_name = "Facility Status"
        verbose_name_plural = "Facility Statuses"
        get_latest_by = "status_date"
        ordering = ('-status_date',)


# Ported from: https://github.com/dimagi/logistics/blob/tz-master/logistics_project/apps/tanzania/models.py#L170
class DeliveryGroupReport(models.Model):
    supply_point = models.CharField(max_length=100, db_index=True)
    quantity = models.IntegerField()
    report_date = models.DateTimeField(default=datetime.now())
    message = models.CharField(max_length=100, db_index=True)
    delivery_group = models.CharField(max_length=1)
    external_id = models.PositiveIntegerField(null=True, db_index=True)

    class Meta:
        ordering = ('-report_date',)

    @classmethod
    def wrap_from_json(cls, obj, location_id):
        obj['supply_point'] = location_id
        obj['external_id'] = obj['id']
        del obj['id']
        return cls(**obj)


# Ported from: https://github.com/dimagi/logistics/blob/tz-master/logistics_project/apps/tanzania/models.py#L170
# https://github.com/dimagi/rapidsms-logistics/blob/master/logistics/warehouse_models.py#L14
class ReportingModel(models.Model):
    """
    A model to encapsulate aggregate (data warehouse) data used by a report.
    """
    date = models.DateTimeField()                   # viewing time period
    supply_point = models.CharField(max_length=100, db_index=True)
    create_date = models.DateTimeField(editable=False)
    update_date = models.DateTimeField(editable=False)
    external_id = models.PositiveIntegerField(db_index=True, null=True)

    def save(self, *args, **kwargs):
        if not self.id:
            self.create_date = datetime.utcnow()
        self.update_date = datetime.utcnow()
        super(ReportingModel, self).save(*args, **kwargs)

    class Meta:
        abstract = True


# Ported from: https://github.com/dimagi/rapidsms-logistics/blob/master/logistics/warehouse_models.py#L44
class SupplyPointWarehouseRecord(models.Model):
    """
    When something gets updated in the warehouse, create a record of having
    done that.
    """
    supply_point = models.CharField(max_length=100, db_index=True)
    create_date = models.DateTimeField()


# Ported from:
# https://github.com/dimagi/logistics/blob/tz-master/logistics_project/apps/tanzania/reporting/models.py#L9
class OrganizationSummary(ReportingModel):
    total_orgs = models.PositiveIntegerField(default=0)
    average_lead_time_in_days = models.FloatField(default=0)

    def __unicode__(self):
        return "%s: %s/%s" % (self.supply_point, self.date.month, self.date.year)


# Ported from:
# https://github.com/dimagi/logistics/blob/tz-master/logistics_project/apps/tanzania/reporting/models.py#L16
class GroupSummary(models.Model):
    """
    Warehouse data related to a particular category of reporting
    (e.g. stock on hand summary)
    """
    org_summary = models.ForeignKey('OrganizationSummary')
    title = models.CharField(max_length=50, blank=True, null=True)  # SOH
    total = models.PositiveIntegerField(default=0)
    responded = models.PositiveIntegerField(default=0)
    on_time = models.PositiveIntegerField(default=0)
    complete = models.PositiveIntegerField(default=0)  # "complete" = submitted or responded
    external_id = models.PositiveIntegerField(db_index=True, null=True)

    @classmethod
    def wrap_form_json(cls, obj, location_id):
        org_summary_id = obj['org_summary']['id']
        del obj['org_summary']['id']
        obj['org_summary']['external_id'] = org_summary_id
        obj['org_summary']['supply_point'] = location_id
        obj['org_summary']['create_date'] = force_to_datetime(obj['org_summary']['create_date'])
        obj['org_summary']['update_date'] = force_to_datetime(obj['org_summary']['update_date'])
        obj['org_summary']['date'] = force_to_datetime(obj['org_summary']['date'])
        try:
            obj['org_summary'] = OrganizationSummary.objects.get(external_id=org_summary_id)
        except OrganizationSummary.DoesNotExist:
            obj['org_summary'] = OrganizationSummary.objects.create(**obj['org_summary'])
        obj['external_id'] = obj['id']
        del obj['id']
        return cls(**obj)

    @property
    def late(self):
        return self.complete - self.on_time

    @property
    def not_responding(self):
        return self.total - self.responded

    def is_delivery_or_supervision_facility(self):
        return self.title in [SupplyPointStatusTypes.DELIVERY_FACILITY,
                              SupplyPointStatusTypes.SUPERVISION_FACILITY]

    @property
    def received(self):
        assert self.is_delivery_or_supervision_facility()
        return self.complete

    @property
    def not_received(self):
        assert self.is_delivery_or_supervision_facility()
        return self.responded - self.complete

    @property
    def sup_received(self):
        assert self.title in SupplyPointStatusTypes.SUPERVISION_FACILITY
        return self.complete

    @property
    def sup_not_received(self):
        assert self.title == SupplyPointStatusTypes.SUPERVISION_FACILITY
        return self.responded - self.complete

    @property
    def del_received(self):
        assert self.title == SupplyPointStatusTypes.DELIVERY_FACILITY
        return self.complete

    @property
    def del_not_received(self):
        assert self.title == SupplyPointStatusTypes.DELIVERY_FACILITY
        return self.responded - self.complete

    @property
    def not_submitted(self):
        assert self.title in [SupplyPointStatusTypes.SOH_FACILITY,
                              SupplyPointStatusTypes.R_AND_R_FACILITY]
        return self.responded - self.complete

    def __unicode__(self):
        return "%s - %s" % (self.org_summary, self.title)


# Ported from:
# https://github.com/dimagi/logistics/blob/tz-master/logistics_project/apps/tanzania/reporting/models.py#L78
class ProductAvailabilityData(ReportingModel):
    product = models.CharField(max_length=100, db_index=True)
    total = models.PositiveIntegerField(default=0)
    with_stock = models.PositiveIntegerField(default=0)
    without_stock = models.PositiveIntegerField(default=0)
    without_data = models.PositiveIntegerField(default=0)

    @classmethod
    def wrap_from_json(cls, obj, domain, location_id):
        product = Product.get_by_code(domain, obj['product'])
        obj['product'] = product._id
        obj['supply_point'] = location_id
        obj['external_id'] = obj['id']
        del obj['id']
        return cls(**obj)


# Ported from:
# https://github.com/dimagi/logistics/blob/tz-master/logistics_project/apps/tanzania/reporting/models.py#L85
class ProductAvailabilityDashboardChart(object):
    label_color = {
        "Stocked out": "#a30808",
        "Not Stocked out": "#7aaa7a",
        "No Stock Data": "#efde7f"
    }
    width = 900
    height = 300
    div = "product_availability_summary_plot_placeholder"
    legenddiv = "product_availability_summary_legend"
    xaxistitle = "Products"
    yaxistitle = "Facilities"


# Ported from:
# https://github.com/dimagi/logistics/blob/tz-master/logistics_project/apps/tanzania/reporting/models.py#L97
class Alert(ReportingModel):
    type = models.CharField(max_length=50, blank=True, null=True)
    number = models.PositiveIntegerField(default=0)
    text = models.TextField()
    url = models.CharField(max_length=100, blank=True, null=True)
    expires = models.DateTimeField()


# Ported from:
# https://github.com/dimagi/logistics/blob/tz-master/logistics_project/apps/tanzania/models.py#L11
class DeliveryGroups(object):
    """
        There are three delivery groups of facilities: A, B, C.
        Every month groups have different roles starting from the state below.
        Submitting group: January = A
        Processing group: January = C
        Delivering group: January = B
        Next month A will be changed to B, B to C and C to B.
    """

    GROUPS = ('A', 'B', 'C')

    def __init__(self, month=None, facs=None):
        self.month = month if month else datetime.utcnow().month
        self.facs = facs

    def current_submitting_group(self, month=None):
        month = month if month else self.month
        return self.GROUPS[(month + 2) % 3]

    def current_processing_group(self, month=None):
        month = month if month else self.month
        return self.current_submitting_group(month=(month + 2))

    def current_delivering_group(self, month=None):
        month = month if month else self.month
        return self.current_submitting_group(month=(month + 1))

    def delivering(self, facs=None, month=None):
        if not facs:
            facs = self.facs
        if not facs:
            return []
        return filter(lambda f: self.current_delivering_group(month) in f.metadata.get('group', None), facs)

    def processing(self, facs=None, month=None):
        if not facs:
            facs = self.facs
        if not facs:
            return []
        return filter(lambda f: self.current_processing_group(month) in f.metadata.get('group', None), facs)

    def submitting(self, facs=None, month=None):
        if not facs:
            facs = self.facs
        if not facs:
            return []
        return filter(lambda f: self.current_submitting_group(month) in f.metadata.get('group', None), facs)


# Ported from:
# https://github.com/dimagi/logistics/blob/tz-master/logistics_project/apps/tanzania/reporting/models.py#L97
class ReportRun(models.Model):
    """
    Log of whenever the warehouse models get updated.
    """
    start = models.DateTimeField()  # the start of the period covered (from a data perspective)
    end = models.DateTimeField()   # the end of the period covered (from a data perspective)
    start_run = models.DateTimeField()        # when this started
    end_run = models.DateTimeField(null=True)  # when this finished
    complete = models.BooleanField(default=False)
    has_error = models.BooleanField(default=False)
    domain = models.CharField(max_length=60)
    location = models.ForeignKey(SQLLocation, null=True)

    @classmethod
    def last_success(cls, domain):
        """
        The last successful execution of a report, or None if no records found.
        """
        qs = cls.objects.filter(complete=True, has_error=False, domain=domain)
        return qs.order_by("-start_run")[0] if qs.count() else None

    @classmethod
    def last_run(cls, domain):
        qs = cls.objects.filter(complete=True, domain=domain)
        return qs.order_by("-start_run")[0] if qs.count() else None


class HistoricalLocationGroup(models.Model):
    location_id = models.ForeignKey(SQLLocation)
    date = models.DateField()
    group = models.CharField(max_length=1)

    class Meta:
        unique_together = ('location_id', 'date', 'group')


class RequisitionReport(models.Model):
    location_id = models.CharField(max_length=100, db_index=True)
    submitted = models.BooleanField(default=False)
    report_date = models.DateTimeField(default=datetime.utcnow)


class SupervisionDocument(models.Model):
    document = models.TextField()
    domain = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    data_type = models.CharField(max_length=100)


class ILSNotes(models.Model):
    location = models.ForeignKey(SQLLocation)
    domain = models.CharField(max_length=100, null=False)
    user_name = models.CharField(max_length=128, null=False)
    user_role = models.CharField(max_length=100, null=True)
    user_phone = models.CharField(max_length=20, null=True)
    date = models.DateTimeField()
    text = models.TextField()
