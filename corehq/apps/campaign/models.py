from django.db import models
from django.utils.translation import gettext_lazy


class Gauge(models.Model):
    CASE = 'case'
    MOBILE_WORKER = 'mobile_worker'

    TYPE_CHOICES = (
        (CASE, gettext_lazy('Case')),
        (MOBILE_WORKER, gettext_lazy('Mobile Worker')),
    )

    type = models.CharField(null=False, blank=False, db_index=True, choices=TYPE_CHOICES)
    case_type = models.CharField(null=True)
