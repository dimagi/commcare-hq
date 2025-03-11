from django.db import models
from django.db.models import Prefetch


class DashboardManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().prefetch_related(
            Prefetch('reports', queryset=DashboardMap.objects.all())
        )


class Dashboard(models.Model):
    """
    Model to store campaign dashboard configuration
    """
    domain = models.CharField(max_length=126, db_index=True, unique=True)

    objects = DashboardManager()

    class Meta:
        app_label = 'campaign'


class DashboardMap(models.Model):
    """
    Configuration for a map/report in a campaign dashboard
    """
    dashboard = models.ForeignKey(
        Dashboard,
        on_delete=models.CASCADE,
        related_name='reports'
    )
    display_order = models.IntegerField(default=0)
    case_type = models.CharField(max_length=126)
    geo_case_property = models.CharField(max_length=126)

    class Meta:
        app_label = 'campaign'
        ordering = ['display_order']
