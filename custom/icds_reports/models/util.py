from __future__ import absolute_import
from __future__ import unicode_literals

import architect
import uuid

from django.db import models
from django.contrib.postgres.fields import ArrayField, JSONField

from dimagi.utils.web import get_ip


class AggregateSQLProfile(models.Model):
    name = models.TextField()
    date = models.DateField(auto_now=True)
    duration = models.PositiveIntegerField()
    last_included_doc_time = models.DateTimeField(null=True)


class UcrTableNameMapping(models.Model):
    table_type = models.TextField(primary_key=True)
    table_name = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        app_label = 'icds_reports'
        db_table = 'ucr_table_name_mapping'


@architect.install(
    'partition',
    type='range',
    subtype='date',
    constraint='month',
    column='time_of_use'
)
class ICDSAuditEntryRecord(models.Model):
    id = models.UUIDField(unique=True, default=uuid.uuid4, primary_key=True)
    username = models.EmailField(db_index=True)
    assigned_location_ids = ArrayField(models.CharField(max_length=255), null=True)
    ip_address = models.GenericIPAddressField(max_length=15, null=True)
    url = models.TextField()
    post_data = JSONField(default=dict)
    get_data = JSONField(default=dict)
    session_key = models.CharField(max_length=32)
    time_of_use = models.DateTimeField(auto_now_add=True)

    class Meta(object):
        app_label = 'icds_reports'
        db_table = 'icds_audit_entry_record'

    @classmethod
    def create_entry(cls, request, couch_user=None, is_login_page=False):
        couch_user = request.couch_user if couch_user is None else couch_user
        record = cls(
            username=couch_user.username,
            assigned_location_ids=couch_user.get_location_ids(getattr(request, 'domain', None)),
            ip_address=get_ip(request),
            url=request.path,
            get_data=request.GET,
            post_data=request.POST if not is_login_page else {},
            session_key=request.session.session_key,
        )
        record.save()
        return record.id


class CitusDashboardException(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    data_source = models.TextField()
    context = JSONField()
    exception = models.TextField()
    notes = models.TextField(blank=True)


class CitusDashboardDiff(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    data_source = models.TextField()
    context = JSONField()
    control = JSONField()
    candidate = JSONField()
    diff = JSONField()
    notes = models.TextField(blank=True)


class CitusDashboardTiming(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    data_source = models.TextField()
    context = JSONField()
    control_duration = models.DecimalField(max_digits=10, decimal_places=3)
    candidate_duration = models.DecimalField(max_digits=10, decimal_places=3)
