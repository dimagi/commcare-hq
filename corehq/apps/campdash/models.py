from django.db import models
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from corehq.apps.domain.models import Domain


class CampaignDashboard(models.Model):
    """
    Model to store campaign dashboard configuration
    """
    domain = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_by = models.CharField(max_length=255)
    created_on = models.DateTimeField(auto_now_add=True)
    modified_on = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'campdash'
        indexes = [
            models.Index(fields=['domain'], name='campdash_domain_idx'),
            models.Index(fields=['is_active'], name='campdash_active_idx'),
            models.Index(fields=['domain', 'is_active'], name='campdash_domain_active_idx'),
        ]
        permissions = [
            ('view_all_campaign_dashboards', 'Can view all campaign dashboards'),
            ('edit_all_campaign_dashboards', 'Can edit all campaign dashboards'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['domain', 'name'],
                name='unique_dashboard_name_per_domain'
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.domain})"


class DashboardGauge(models.Model):
    """
    Model to store gauge configuration for a campaign dashboard
    """
    GAUGE_TYPES = (
        ('progress', gettext_lazy('Progress')),
        ('percentage', gettext_lazy('Percentage')),
        ('count', gettext_lazy('Count')),
    )

    dashboard = models.ForeignKey(CampaignDashboard, on_delete=models.CASCADE, related_name='gauges')
    title = models.CharField(max_length=255)
    gauge_type = models.CharField(max_length=20, choices=GAUGE_TYPES, default='progress')
    data_source = models.CharField(max_length=255, blank=True, null=True)
    min_value = models.IntegerField(default=0)
    max_value = models.IntegerField(default=100)
    current_value = models.IntegerField(default=0)
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        app_label = 'campdash'
        ordering = ['display_order']
        indexes = [
            models.Index(fields=['display_order'], name='campdash_gauge_order_idx'),
        ]
        permissions = [
            ('configure_gauges', 'Can configure dashboard gauges'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(min_value__lt=models.F('max_value')),
                name='gauge_min_less_than_max'
            ),
            models.CheckConstraint(
                check=models.Q(current_value__gte=models.F('min_value'), 
                               current_value__lte=models.F('max_value')),
                name='gauge_value_in_range'
            ),
        ]

    def __str__(self):
        return f"{self.title} - {self.dashboard.name}"

    def clean(self):
        """
        Validate the gauge values
        """
        from django.core.exceptions import ValidationError
        
        if self.min_value >= self.max_value:
            raise ValidationError({'min_value': _('Minimum value must be less than maximum value')})
        
        if self.current_value < self.min_value or self.current_value > self.max_value:
            raise ValidationError({'current_value': _('Current value must be between minimum and maximum values')})


class DashboardReport(models.Model):
    """
    Model to store report configuration for a campaign dashboard
    """
    REPORT_TYPES = (
        ('table', gettext_lazy('Table')),
        ('chart', gettext_lazy('Chart')),
        ('list', gettext_lazy('List')),
    )

    dashboard = models.ForeignKey(CampaignDashboard, on_delete=models.CASCADE, related_name='reports')
    title = models.CharField(max_length=255)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES, default='table')
    data_source = models.CharField(max_length=255, blank=True, null=True)
    config = models.JSONField(default=dict, blank=True)
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        app_label = 'campdash'
        ordering = ['display_order']
        indexes = [
            models.Index(fields=['display_order'], name='campdash_report_order_idx'),
        ]
        permissions = [
            ('configure_reports', 'Can configure dashboard reports'),
        ]

    def __str__(self):
        return f"{self.title} - {self.dashboard.name}"


class DashboardMap(models.Model):
    """
    Model to store map configuration for a campaign dashboard
    """
    MAP_TYPES = (
        ('markers', gettext_lazy('Markers')),
        ('heatmap', gettext_lazy('Heat Map')),
        ('choropleth', gettext_lazy('Choropleth')),
    )

    dashboard = models.ForeignKey(CampaignDashboard, on_delete=models.CASCADE, related_name='maps')
    title = models.CharField(max_length=255)
    map_type = models.CharField(max_length=20, choices=MAP_TYPES, default='markers')
    data_source = models.CharField(max_length=255, blank=True, null=True)
    config = models.JSONField(default=dict, blank=True)
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        app_label = 'campdash'
        ordering = ['display_order']
        indexes = [
            models.Index(fields=['display_order'], name='campdash_map_order_idx'),
        ]
        permissions = [
            ('configure_maps', 'Can configure dashboard maps'),
        ]

    def __str__(self):
        return f"{self.title} - {self.dashboard.name}"
