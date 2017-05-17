from __future__ import unicode_literals
import json
from django.db import models
from corehq.apps.motech.models import ConnectedAccount


class OpenmrsConcept(models.Model):
    uuid = models.CharField(max_length=256)
    account = models.ForeignKey(ConnectedAccount, on_delete=models.CASCADE)
    display = models.TextField()
    concept_class = models.CharField(max_length=256)
    retired = models.BooleanField()
    datatype = models.CharField(max_length=256)
    answers = models.ManyToManyField('OpenmrsConcept')
    descriptions = models.TextField(validators=(json.dumps,))
    names = models.TextField(validators=(json.dumps,))

    class Meta(object):
        unique_together = [('account', 'uuid')]

    def __str__(self):
        return 'OpenMRS Concept {}: {}'.format(self.uuid, self.display)
