from django.db import models
from django.utils.translation import gettext as _

import jsonfield
from django_tables2 import columns

from corehq.apps.hqwebapp.tables.htmx import BaseHtmxTable
from corehq.motech.models import ConnectionSettings


class UserDataStore(object):
    CUSTOM_USER_DATA = 'custom_user_data'
    USER_CASE = 'user_case'
    OTHER_CASE_TYPE = 'other_case_type'
    CHOICES = [
        (CUSTOM_USER_DATA, _('Custom User Data')),
        (USER_CASE, _('User Case')),
        (OTHER_CASE_TYPE, _('Other Case Type')),
    ]


class KycProviders(models.TextChoices):
    MTN_KYC = 'mtn_kyc', _('MTN KYC')


class KycConfig(models.Model):
    domain = models.CharField(max_length=126, db_index=True)
    user_data_store = models.CharField(max_length=25, choices=UserDataStore.CHOICES)
    other_case_type = models.CharField(max_length=126, null=True)
    api_field_to_user_data_map = jsonfield.JSONField(default=list)
    connection_settings = models.ForeignKey(ConnectionSettings, on_delete=models.PROTECT)
    provider = models.CharField(max_length=25, choices=KycProviders.choices, default=KycProviders.MTN_KYC)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['domain', 'provider'], name='unique_domain_provider'),
        ]


class KycVerifyTable(BaseHtmxTable):
    class Meta(BaseHtmxTable.Meta):
        pass

    verify_select = columns.CheckBoxColumn(
        accessor='id',
        attrs={
            'th__input': {'name': 'select_all'},
            'td__input': {'name': 'selection'}
        }
    )
    first_name = columns.Column(
        verbose_name=_("First Name"),
    )
    last_name = columns.Column(
        verbose_name=_("Last Name"),
    )
    phone_number = columns.Column(
        verbose_name=_("Phone Number"),
    )
    email = columns.Column(
        verbose_name=_("Email Address"),
    )
    national_id_number = columns.Column(
        verbose_name=_("National ID Number"),
    )
    street_address = columns.Column(
        verbose_name=_("Street Address"),
    )
    city = columns.Column(
        verbose_name=_("City"),
    )
    post_code = columns.Column(
        verbose_name=_("Post Code"),
    )
    country = columns.Column(
        verbose_name=_("Country"),
    )
    verify_btn = columns.TemplateColumn(
        template_name='kyc/partials/kyc_verify_button.html',
        verbose_name=_("Verify"),
    )
