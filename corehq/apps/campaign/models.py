from django.db import models

from corehq.apps.userreports.models import ReportConfiguration


class Dashboard(models.Model):
    """
    Model to store campaign dashboard configuration
    """
    domain = models.CharField(max_length=126, db_index=True, unique=True)

    class Meta:
        app_label = 'campaign'


class DashboardMap(models.Model):
    """
    Configuration for a map in a campaign dashboard
    """
    dashboard = models.ForeignKey(
        Dashboard,
        on_delete=models.CASCADE,
        related_name='maps'
    )
    display_order = models.IntegerField(default=0)
    case_type = models.CharField(max_length=255)
    geo_case_property = models.CharField(max_length=255)

    class Meta:
        app_label = 'campaign'
        ordering = ['display_order']


class DashboardReport(models.Model):
    """
    Configuration for a report in a campaign dashboard
    """
    dashboard = models.ForeignKey(
        Dashboard,
        on_delete=models.CASCADE,
        related_name='reports'
    )
    display_order = models.IntegerField(default=0)
    report_configuration_id = models.CharField(max_length=36)

    class Meta:
        app_label = 'campaign'
        ordering = ['display_order']

    @property
    def report_configuration(self):
        return ReportConfiguration.get(self.report_configuration_id)
