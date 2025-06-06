from itertools import chain

from django.db import models
from django.forms import model_to_dict
from django.utils.translation import gettext_lazy as _

from jsonfield.fields import JSONField

from corehq.apps.userreports.models import ReportConfiguration
from corehq.util.view_utils import absolute_reverse


class Dashboard(models.Model):
    """
    Model to store campaign dashboard configuration
    """
    domain = models.CharField(max_length=126, db_index=True, unique=True)

    class Meta:
        app_label = 'campaign'

    def get_map_report_widgets_by_tab(self):
        """
        Returns a dictionary of map and report widgets by tab.
        """
        widgets_by_tab = {tab: [] for tab in DashboardTab.values}
        for instance in sorted(
            chain(self.maps.all(), self.reports.all()),
            key=lambda inst: inst.display_order
        ):
            widgets_by_tab[instance.dashboard_tab].append(instance.to_widget())
        return widgets_by_tab


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

    def to_widget(self):
        return model_to_widget(
            self,
            exclude=['dashboard_tab', 'display_order'],
        )


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

    @property
    def url(self):
        """
        Returns the URL of the view for the user-configurable report.

        e.g. http://example.org/a/test-domain/reports/configurable/abc123/
        """
        return absolute_reverse(
            'configurable',
            args=[self.dashboard.domain, self.report_configuration_id],
        )

    def to_widget(self):
        return model_to_widget(
            self,
            exclude=['dashboard_tab', 'display_order'],
            properties=['url'],
        )


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

    def to_widget(self):
        return model_to_widget(
            self,
            exclude=['dashboard_tab', 'display_order'],
        )


class WidgetType(models.TextChoices):
    GAUGE = 'gauge', _('Gauge')
    MAP = 'map', _('Map')
    REPORT = 'report', _('Report')

    @classmethod
    def get_form_class(cls, widget_type):
        from corehq.apps.campaign.forms import (
            DashboardGaugeForm,
            DashboardMapForm,
            DashboardReportForm,
        )
        form_classes = {
            cls.GAUGE: DashboardGaugeForm,
            cls.MAP: DashboardMapForm,
            cls.REPORT: DashboardReportForm,
        }
        return form_classes[widget_type]

    @classmethod
    def get_model_class(cls, widget_type):
        return cls.get_form_class(widget_type).Meta.model


def model_to_widget(instance, fields=None, exclude=None, properties=()):
    """
    Like model_to_dict, but adds 'widget_type', 'dashboard', and
    properties given in ``properties``.
    """
    widget = model_to_dict(instance, fields, exclude)
    widget.update(
        {prop: getattr(instance, prop) for prop in properties},
        widget_type=instance.__class__.__name__,
        dashboard=model_to_dict(instance.dashboard, exclude=['id']),
    )
    return widget
