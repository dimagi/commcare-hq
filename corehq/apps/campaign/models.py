from django.db import models
from django.utils.translation import gettext_lazy as _
from jsonfield.fields import JSONField

from corehq.apps.userreports.models import ReportConfiguration


class Dashboard(models.Model):
    """
    Model to store campaign dashboard configuration
    """
    domain = models.CharField(max_length=126, db_index=True, unique=True)

    class Meta:
        app_label = 'campaign'


class DashboardTab(models.TextChoices):
    """
    The tab on which a dashboard widget is displayed
    """
    CASES = 'cases', _('Cases')
    MOBILE_WORKERS = 'mobile_workers', _('Mobile Workers')


class DashboardWidgetBase(models.Model):
    """
    Base class for dashboard widgets
    """
    title = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    dashboard_tab = models.CharField(max_length=14, choices=DashboardTab.choices)
    display_order = models.IntegerField(default=0)
    dashboard = models.ForeignKey(
        Dashboard,
        on_delete=models.CASCADE,
    )

    class Meta:
        abstract = True
        ordering = ['dashboard_tab', 'display_order']


class DashboardMap(DashboardWidgetBase):
    """
    Configuration for a map in a campaign dashboard
    """
    dashboard = models.ForeignKey(
        Dashboard,
        on_delete=models.CASCADE,
        related_name='maps',
    )
    case_type = models.CharField(max_length=255)
    geo_case_property = models.CharField(max_length=255)

    class Meta(DashboardWidgetBase.Meta):
        app_label = 'campaign'


class DashboardReport(DashboardWidgetBase):
    """
    Configuration for a report in a campaign dashboard
    """
    dashboard = models.ForeignKey(
        Dashboard,
        on_delete=models.CASCADE,
        related_name='reports',
    )
    report_configuration_id = models.CharField(max_length=36)

    class Meta(DashboardWidgetBase.Meta):
        app_label = 'campaign'

    @property
    def report_configuration(self):
        return ReportConfiguration.get(self.report_configuration_id)


class DashboardGauge(DashboardWidgetBase):
    """
    Configuration for a gauge in a campaign dashboard
    """
    dashboard = models.ForeignKey(
        Dashboard,
        on_delete=models.CASCADE,
        related_name='gauges',
    )

    # cases gauge fields
    case_type = models.CharField(max_length=255, null=True, blank=True)

    # one of the metric from the ones available as set in GAUGE_METRICS
    # ToDo: add choices=GAUGE_METRICS once populated with relevant metrics
    metric = models.CharField(max_length=255, null=False, blank=False)

    # optional additional configuration set to customize gauge appearance
    configuration = JSONField(default=dict)
