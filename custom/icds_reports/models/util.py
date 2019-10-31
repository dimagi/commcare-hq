import uuid

from django.contrib.postgres.fields import ArrayField, JSONField
from django.db import models

import architect

from dimagi.utils.web import get_ip

from corehq.sql_db.util import get_db_aliases_for_partitioned_query


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
    time_of_use = models.DateTimeField(auto_now_add=True, db_index=True)
    response_code = models.IntegerField(null=True)

    class Meta(object):
        app_label = 'icds_reports'
        db_table = 'icds_audit_entry_record'

    @classmethod
    def create_entry(cls, request, response, couch_user=None, is_login_page=False):
        couch_user = request.couch_user if couch_user is None else couch_user
        record = cls(
            username=couch_user.username,
            assigned_location_ids=couch_user.get_location_ids(getattr(request, 'domain', None)),
            ip_address=get_ip(request),
            url=request.path,
            get_data=request.GET,
            post_data=request.POST if not is_login_page else {},
            session_key=request.session.session_key,
            response_code=response.status_code if response else None
        )
        record.save()
        return record.id


class AggregationRecord(models.Model):
    agg_date = models.DateField()
    run_date = models.DateField(auto_now_add=True)
    state_ids = ArrayField(models.CharField(max_length=255), null=True)
    agg_uuid = models.UUIDField(unique=True, default=uuid.uuid4)


class UcrReconciliationStatus(models.Model):
    XMLNS = 'xmlns'
    CASE_TYPE = 'case_type'

    db_alias = models.CharField(max_length=10)
    day = models.DateField()
    table_id = models.TextField()
    doc_type = models.CharField(
        max_length=10,
        choices=(
            (CASE_TYPE, 'Case Type'),
            (XMLNS, 'XMLNS'),
        )
    )
    doc_type_filter = models.TextField(help_text="Either an XMLNS or case type")
    last_processed_date = models.DateTimeField(null=True)
    verified_date = models.DateTimeField(null=True)

    @property
    def is_form_ucr(self):
        return self.doc_type == self.XMLNS

    @classmethod
    def setup_days_records(cls, day):
        UCR_MAPPING = (
            ('static-usage_forms', 'xmlns', 'http://openrosa.org/formdesigner/66d52f84d606567ea29d5fae88f569d2763b8b62'),
            ('static-usage_forms', 'xmlns', 'http://openrosa.org/formdesigner/b183124a25f2a0ceab266e4564d3526199ac4d75'),
            ('static-usage_forms', 'xmlns', 'http://openrosa.org/formdesigner/F1B73934-8B70-4CEE-B462-3E4C81F80E4A'),
            ('static-usage_forms', 'xmlns', 'http://openrosa.org/formdesigner/2864010F-B1B1-4711-8C59-D5B2B81D65DB'),
            ('static-usage_forms', 'xmlns', 'http://openrosa.org/formdesigner/376FA2E1-6FD1-4C9E-ACB4-E046038CD5E2'),
            ('static-usage_forms', 'xmlns', 'http://openrosa.org/formdesigner/D4A7ABD2-A7B8-431B-A88B-38245173B0AE'),
            ('static-usage_forms', 'xmlns', 'http://openrosa.org/formdesigner/89097FB1-6C08-48BA-95B2-67BCF0C5091D'),
            ('static-usage_forms', 'xmlns', 'http://openrosa.org/formdesigner/792DAF2B-E117-424A-A673-34E1513ABD88'),
            ('static-usage_forms', 'xmlns', 'http://openrosa.org/formdesigner/619B942A-362E-43DE-8650-ED37026D9AC4'),
            ('static-usage_forms', 'xmlns', 'http://openrosa.org/formdesigner/1D568275-1D19-46DB-8C54-2C9765DF6335'),
            ('static-usage_forms', 'xmlns', 'http://openrosa.org/formdesigner/362f76b242d0cfdcec66776f9586dc3620e9cce5'),
            ('static-usage_forms', 'xmlns', 'http://openrosa.org/formdesigner/756ec44475658f3f463f8012632def2bc9fbe731'),
            ('static-dashboard_growth_monitoring_forms', 'xmlns', 'http://openrosa.org/formdesigner/7a55754119359466b1951d7251068bd4f45e73c3'),
            ('static-awc_mgt_forms', 'xmlns', 'http://openrosa.org/formdesigner/D8EED5E3-88CD-430E-984F-45F14E76A551'),
            ('static-cbe_form', 'xmlns', 'http://openrosa.org/formdesigner/61238C23-7059-446D-8A9C-34107642CBB2'),
            ('static-cbe_form', 'xmlns', 'http://openrosa.org/formdesigner/D305345E-94AE-4A23-899E-22D05EECF1AD'),
            ('static-infrastructure_form_v2', 'xmlns', 'http://openrosa.org/formdesigner/BEB94AFD-E063-46CC-AA75-BECD3C0FC20C'),
            ('static-it_report_follow_issue', 'xmlns', 'http://openrosa.org/formdesigner/0AD845EA-69E8-4479-9140-4072A14AA0E5'),
            ('static-it_report_follow_issue', 'xmlns', 'http://openrosa.org/formdesigner/32083FFC-9AD7-46A8-B256-1B9431469262'),
            ('static-ls_home_visit_forms_filled', 'xmlns', 'http://openrosa.org/formdesigner/327e11f3c04dfc0a7fea9ee57d7bb7be83475309'),
            ('static-ls_vhnd_form', 'xmlns', 'http://openrosa.org/formdesigner/b8273b657bb097eb6ba822663b7191ff6bc276ff'),
            ('static-vhnd_form', 'xmlns', 'http://openrosa.org/formdesigner/A1C9EF1B-8B42-43AB-BA81-9484DB9D8293'),
            ('static-visitorbook_forms', 'xmlns', 'http://openrosa.org/formdesigner/08583F46-ED60-4864-B54F-CA725D5C230E'),
            ('static-commcare_user_cases', 'case_type', 'commcare-user'),
            ('static-ccs_record_cases', 'case_type', 'ccs_record'),
            ('static-child_health_cases', 'case_type', 'child_health'),
            ('static-hardware_cases', 'case_type', 'hardware'),
            ('static-household_cases', 'case_type', 'household'),
            ('static-person_cases_v3', 'case_type', 'person'),
            ('static-tasks_cases', 'case_type', 'tasks'),
            ('static-tech_issue_cases', 'case_type', 'tech_issue'),
        )
        for mapping in UCR_MAPPING:
            for db in get_db_aliases_for_partitioned_query():
                cls.objects.get_or_create(
                    db_alias=db,
                    day=day,
                    table_id=mapping[0],
                    doc_type=mapping[1],
                    doc_type_filter=mapping[2],
                )

    class Meta:
        unique_together = ('db_alias', 'day', 'table_id', 'doc_type_filter')
