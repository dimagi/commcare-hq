from django.contrib import admin
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy

from corehq.apps.app_manager import const


class TemplateAppSector(models.Model):
    """A shared sector label for the template app catalog."""

    name = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower('name'), name='unique_template_app_sector_name_ci'),
        ]

    def __str__(self):
        return self.name


class ExchangeApplication(models.Model):
    """Catalog entry for a template app.
    Historically named for the App Exchange page; the feature is now called Template Apps.
    """

    class Category(models.TextChoices):
        STARTER_APP = 'starter_app', gettext_lazy('Starter App')
        FEATURE_TEMPLATE = 'feature_template', gettext_lazy('Feature Template')

    domain = models.CharField(max_length=255, null=False)
    app_id = models.CharField(max_length=255, null=False)
    help_link = models.CharField(max_length=255, null=True)
    category = models.CharField(max_length=32, choices=Category.choices)
    sectors = models.ManyToManyField(TemplateAppSector, related_name='exchange_applications', blank=True)
    description = models.TextField(null=True, blank=True)
    minimum_plan_edition = models.CharField(max_length=25, choices=const.get_template_app_plan_choices)

    class Meta(object):
        unique_together = ('domain', 'app_id')


class ExchangeApplicationAdmin(admin.ModelAdmin):
    model = ExchangeApplication
    list_display = ['domain', 'app_id', 'category', 'minimum_plan_edition', 'help_link']
    list_filter = ['domain', 'app_id']


admin.site.register(ExchangeApplication, ExchangeApplicationAdmin)
