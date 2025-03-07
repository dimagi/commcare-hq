from django.db import models
from django.db.models import Prefetch


class CampaignDashboardManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().prefetch_related(
            Prefetch('reports', queryset=DashboardReport.objects.all())
        )


class CampaignDashboard(models.Model):
    """
    Model to store campaign dashboard configuration
    """
    domain = models.CharField(max_length=126, db_index=True, unique=True)

    objects = CampaignDashboardManager()

    class Meta:
        app_label = 'campdash'


class DashboardReport(models.Model):
    """
    Model to store report configuration for a campaign dashboard
    """
    dashboard = models.ForeignKey(
        CampaignDashboard,
        on_delete=models.CASCADE,
        related_name='reports'
    )
    display_order = models.IntegerField(default=0)

    # Stores corehq.apps.userreports.models.ReportConfiguration._id
    report_configuration = models.CharField(max_length=126)

    class Meta:
        app_label = 'campdash'
        ordering = ['display_order']
        indexes = [
            models.Index(
                fields=['display_order'],
                name='campdash_report_order_idx',
            ),
        ]
