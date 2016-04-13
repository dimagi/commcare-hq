from datetime import datetime

import json_field
from django.dispatch.dispatcher import receiver
from corehq.apps.domain.signals import commcare_domain_pre_delete
from corehq.apps.locations.signals import location_edited
from dimagi.ext.couchdbkit import Document, BooleanProperty, StringProperty
from django.db import models, connection

from casexml.apps.stock.models import DocDomainMapping
from corehq.apps.locations.models import SQLLocation
from custom.utils.utils import add_to_module_map
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
            add_to_module_map(self.domain, 'custom.ilsgateway')


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
    TRANS_FACILITY = "trans_fac"

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
        TRANS_FACILITY: {
            SupplyPointStatusValues.SUBMITTED: "Transfer Stock Submitted",
            SupplyPointStatusValues.NOT_SUBMITTED: "Transfer Stock Not Submitted",
            SupplyPointStatusValues.REMINDER_SENT: "Transfer Reminder Sent"
        }
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
    location_id = models.CharField(max_length=100, db_index=True)
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

    class Meta:
        app_label = 'ilsgateway'
        verbose_name = "Facility Status"
        verbose_name_plural = "Facility Statuses"
        get_latest_by = "status_date"
        ordering = ('-status_date',)


# Ported from: https://github.com/dimagi/logistics/blob/tz-master/logistics_project/apps/tanzania/models.py#L170
class DeliveryGroupReport(models.Model):
    location_id = models.CharField(max_length=100, db_index=True)
    quantity = models.IntegerField()
    report_date = models.DateTimeField(default=datetime.utcnow)
    message = models.CharField(max_length=100, db_index=True)
    delivery_group = models.CharField(max_length=1)
    external_id = models.PositiveIntegerField(null=True, db_index=True)

    class Meta:
        app_label = 'ilsgateway'
        ordering = ('-report_date',)


# Ported from: https://github.com/dimagi/logistics/blob/tz-master/logistics_project/apps/tanzania/models.py#L170
# https://github.com/dimagi/rapidsms-logistics/blob/master/logistics/warehouse_models.py#L14
class ReportingModel(models.Model):
    """
    A model to encapsulate aggregate (data warehouse) data used by a report.
    """
    date = models.DateTimeField()                   # viewing time period
    location_id = models.CharField(max_length=100, db_index=True)
    create_date = models.DateTimeField(editable=False)
    update_date = models.DateTimeField(editable=False)
    external_id = models.PositiveIntegerField(db_index=True, null=True)

    class Meta:
        app_label = 'ilsgateway'

    def save(self, *args, **kwargs):
        if not self.id:
            self.create_date = datetime.utcnow()
        self.update_date = datetime.utcnow()
        super(ReportingModel, self).save(*args, **kwargs)

    class Meta:
        abstract = True


# Ported from:
# https://github.com/dimagi/logistics/blob/tz-master/logistics_project/apps/tanzania/reporting/models.py#L9
class OrganizationSummary(ReportingModel):
    total_orgs = models.PositiveIntegerField(default=0)
    average_lead_time_in_days = models.FloatField(default=0)

    class Meta:
        app_label = 'ilsgateway'

    def __unicode__(self):
        return "%s: %s/%s" % (self.location_id, self.date.month, self.date.year)


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

    class Meta:
        app_label = 'ilsgateway'

    @classmethod
    def wrap_form_json(cls, obj, location_id):
        org_summary_id = obj['org_summary']['id']
        del obj['org_summary']['id']
        obj['org_summary']['external_id'] = org_summary_id
        obj['org_summary']['location_id'] = location_id
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

    class Meta:
        app_label = 'ilsgateway'

    def __str__(self):
        return 'ProductAvailabilityData(date={}, product={}, total={}, with_stock={}, without_stock={}, ' \
               'without_data={})'.format(self.date, self.product, self.total, self.with_stock,
                                         self.without_stock, self.without_data)


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

    class Meta:
        app_label = 'ilsgateway'


# Ported from:
# https://github.com/dimagi/logistics/blob/tz-master/logistics_project/apps/tanzania/reporting/models.py#L97
class Alert(ReportingModel):
    type = models.CharField(max_length=50, blank=True, null=True)
    number = models.PositiveIntegerField(default=0)
    text = models.TextField()
    url = models.CharField(max_length=100, blank=True, null=True)
    expires = models.DateTimeField()

    class Meta:
        app_label = 'ilsgateway'


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
        return filter(lambda f: self.current_delivering_group(month) == f.metadata.get('group', None), facs)

    def processing(self, facs=None, month=None):
        if not facs:
            facs = self.facs
        if not facs:
            return []
        return filter(lambda f: self.current_processing_group(month) == f.metadata.get('group', None), facs)

    def submitting(self, facs=None, month=None):
        if not facs:
            facs = self.facs
        if not facs:
            return []
        return filter(lambda f: self.current_submitting_group(month) == f.metadata.get('group', None), facs)


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
    location = models.ForeignKey(SQLLocation, null=True, on_delete=models.PROTECT)

    class Meta:
        app_label = 'ilsgateway'

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


class RequisitionReport(models.Model):
    location_id = models.CharField(max_length=100, db_index=True)
    submitted = models.BooleanField(default=False)
    report_date = models.DateTimeField(default=datetime.utcnow)

    class Meta:
        app_label = 'ilsgateway'


class SupervisionDocument(models.Model):
    document = models.TextField()
    domain = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    data_type = models.CharField(max_length=100)

    class Meta:
        app_label = 'ilsgateway'


class ILSNotes(models.Model):
    location = models.ForeignKey(SQLLocation, on_delete=models.PROTECT)
    domain = models.CharField(max_length=100, null=False)
    user_name = models.CharField(max_length=128, null=False)
    user_role = models.CharField(max_length=100, null=True)
    user_phone = models.CharField(max_length=20, null=True)
    date = models.DateTimeField()
    text = models.TextField()

    class Meta:
        app_label = 'ilsgateway'


class PendingReportingDataRecalculation(models.Model):
    domain = models.CharField(max_length=128)
    sql_location = models.ForeignKey(SQLLocation)
    type = models.CharField(max_length=128)
    data = json_field.JSONField()

    class Meta:
        app_label = 'ilsgateway'


class SLABConfig(models.Model):
    is_pilot = models.BooleanField(default=False)
    sql_location = models.ForeignKey(SQLLocation, null=False, unique=True)
    closest_supply_points = models.ManyToManyField(SQLLocation, related_name='+')

    class Meta:
        app_label = 'ilsgateway'


class OneOffTaskProgress(models.Model):
    domain = models.CharField(max_length=128)
    task_name = models.CharField(max_length=128)
    last_synced_object_id = models.CharField(max_length=128, null=True)
    complete = models.BooleanField(default=False)
    progress = models.IntegerField(default=0)
    total = models.IntegerField(default=0)

    class Meta:
        app_label = 'ilsgateway'


@receiver(commcare_domain_pre_delete)
def domain_pre_delete_receiver(domain, **kwargs):
    from corehq.apps.domain.deletion import ModelDeletion, CustomDeletion

    def _delete_ilsgateway_data(domain_name):
        locations_ids = SQLLocation.objects.filter(domain=domain_name).values_list('location_id', flat=True)
        if not locations_ids:
            return

        DeliveryGroupReport.objects.filter(location_id__in=locations_ids).delete()

        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM ilsgateway_alert WHERE location_id IN "
                "(SELECT location_id FROM locations_sqllocation WHERE domain=%s)", [domain_name]
            )
            cursor.execute(
                "DELETE FROM ilsgateway_groupsummary WHERE org_summary_id IN "
                "(SELECT id FROM ilsgateway_organizationsummary WHERE location_id IN "
                "(SELECT location_id FROM locations_sqllocation WHERE domain=%s))", [domain_name]
            )

            cursor.execute(
                "DELETE FROM ilsgateway_organizationsummary WHERE location_id IN "
                "(SELECT location_id FROM locations_sqllocation WHERE domain=%s)", [domain_name]
            )

            cursor.execute(
                "DELETE FROM ilsgateway_productavailabilitydata WHERE location_id IN "
                "(SELECT location_id FROM locations_sqllocation WHERE domain=%s)", [domain_name]
            )

            cursor.execute(
                "DELETE FROM ilsgateway_supplypointstatus WHERE location_id IN "
                "(SELECT location_id FROM locations_sqllocation WHERE domain=%s)", [domain_name]
            )

    return [
        CustomDeletion('ilsgateway', _delete_ilsgateway_data),
        ModelDeletion('ilsgateway', 'ReportRun', 'domain'),
        ModelDeletion('ilsgateway', 'ILSNotes', 'domain'),
        ModelDeletion('ilsgateway', 'SupervisionDocument', 'domain'),
    ]


@receiver(location_edited)
def location_edited_receiver(sender, loc, moved, **kwargs):
    from custom.ilsgateway.utils import last_location_group
    config = ILSGatewayConfig.for_domain(loc.domain)
    if not config or not config.enabled:
        return

    last_run = ReportRun.last_success(loc.domain)
    if not last_run:
        return

    if moved:
        PendingReportingDataRecalculation.objects.create(
            domain=loc.domain,
            type='parent_change',
            sql_location=loc.sql_location,
            data={'previous_parent': loc.previous_parents[-1], 'current_parent': loc.parent_id}
        )

    group = last_location_group(loc)
    if not loc.sql_location.location_type.administrative and group != loc.metadata['group']:
        PendingReportingDataRecalculation.objects.create(
            domain=loc.domain,
            type='group_change',
            sql_location=loc.sql_location,
            data={'previous_group': group, 'current_group': loc.metadata['group']}
        )
