from django.db import models


class CampaignDashboard(models.Model):
    """
    Model to store campaign dashboard configuration
    """
    domain = models.CharField(max_length=126, db_index=True, unique=True)

    class Meta:
        app_label = 'campdash'


class DashboardMap(models.Model):

    dashboard = models.ForeignKey(
        CampaignDashboard,
        on_delete=models.CASCADE,
        related_name='campaign_maps'
    )
    report_configuration = models.CharField(max_length=126)
    display_order = models.IntegerField(default=1)

    class Meta:
        app_label = 'campdash'
        ordering = ['display_order']
        indexes = [
            models.Index(fields=['display_order'], name='campdash_map_report_order_idx'),
        ]
