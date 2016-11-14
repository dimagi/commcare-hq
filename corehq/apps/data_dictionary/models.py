from django.db import models

PROPERTY_TYPE_CHOICES = (
    ('Date', 'Date'),
    ('Plain', 'Plain'),
    ('Number', 'Number'),
    ('Select', 'Select'),
    ('Integer', 'Integer'),
    ('', 'No Type Currently Selected')
)


class CaseType(models.Model):
    domain = models.CharField(max_length=255)
    name = models.CharField(max_length=255)

    class Meta:
        unique_together = ('domain', 'name')


class CaseProperty(models.Model):
    case_type = models.ForeignKey(
        CaseType,
        on_delete=models.CASCADE,
        related_name='properties',
        related_query_name='property'
    )
    name = models.CharField(max_length=255)
    description = models.TextField()
    deprecated = models.BooleanField(default=False)
    type = models.CharField(
        choices=PROPERTY_TYPE_CHOICES,
        max_length=20,
        default=''
    )

    class Meta:
        unique_together = ('case_type', 'name')
