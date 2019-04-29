# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import uuid

from django.db import models


class CaseTemplate(models.Model):
    template_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.CharField(max_length=256, null=False, blank=False, db_index=True)
    name = models.CharField(max_length=256, null=False)
    comment = models.TextField(null=True)

    def get_template_xml(self):
        """get case xml from the blobdb
        """
        pass

    def save_template_xml(self, cases):
        """saves to the blobdb
        """
        pass


class CaseTemplateInstanceCase(models.Model):
    template = models.ForeignKey(CaseTemplate, on_delete=models.CASCADE, related_name='cases')
    case_id = models.CharField(max_length=255, unique=True, db_index=True)
