from django.db import models

PROPERTY_TYPE_CHOICES = (
    ('date', 'Date'),
    ('plain', 'Plain'),
    ('number', 'Number'),
    ('select', 'Select'),
    ('integer', 'Integer'),
    ('', 'No Type Currently Selected')
)


class CaseType(models.Model):
    domain = models.CharField(max_length=255, default=None)
    name = models.CharField(max_length=255, default=None)
    description = models.TextField(default='', blank=True)
    fully_generated = models.BooleanField(default=False)

    class Meta:
        unique_together = ('domain', 'name')


class CaseProperty(models.Model):
    case_type = models.ForeignKey(
        CaseType,
        on_delete=models.CASCADE,
        related_name='properties',
        related_query_name='property'
    )
    name = models.CharField(max_length=255, default=None)
    description = models.TextField(default='', blank=True)
    deprecated = models.BooleanField(default=False)
    data_type = models.CharField(
        choices=PROPERTY_TYPE_CHOICES,
        max_length=20,
        default='',
        blank=True
    )

    class Meta:
        unique_together = ('case_type', 'name')
