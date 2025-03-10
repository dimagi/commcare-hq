from django.db import models
from django.db.models import Prefetch

from corehq.apps.userreports.models import ReportConfiguration


class DashboardManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().prefetch_related(
            Prefetch('reports', queryset=DashboardMapReport.objects.all())
        )


class Dashboard(models.Model):
    """
    Model to store campaign dashboard configuration
    """
    domain = models.CharField(max_length=126, db_index=True, unique=True)

    objects = DashboardManager()

    class Meta:
        app_label = 'campaign'


class DashboardMapReport(models.Model):
    """
    Configuration for a map/report in a campaign dashboard
    """
    dashboard = models.ForeignKey(
        Dashboard,
        on_delete=models.CASCADE,
        related_name='reports'
    )
    display_order = models.IntegerField(default=0)
    report_configuration_id = models.CharField(max_length=126)

    class Meta:
        app_label = 'campaign'
        ordering = ['display_order']

    @property
    def report_configuration(self):
        return ReportConfiguration.get(self.report_configuration_id)

    @property
    def is_map(self):
        return self.report_configuration.report_type == 'map'
