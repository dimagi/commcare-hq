from django.db import models


class ConsumerForm(models.Model):
    domain = models.CharField(max_length=126, null=False, db_index=True)
    slug = models.CharField(max_length=126, null=False, db_index=True)

    class Meta:
        unique_together = ('domain', 'slug')
