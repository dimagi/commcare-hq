# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from datetime import date

from django.db import models, migrations
from django.db.models import F, Q

from corehq.sql_db.operations import HqRunPython


def confirm_no_mismatched_subscription_credit(apps, schema_editor):
    if apps.get_model('accounting', 'CreditLine').objects.filter(
        product_type__isnull=False,
        subscription__isnull=False,
    ).exclude(
        product_type=F('subscription__plan_version__product_rate__product__product_type'),
    ).exclude(
        balance=0,
    ).exclude(
        subscription__is_hidden_to_ops=True,
    ).exists():
        raise Exception("""

Running this migration will make previously inaccessible subscription credit usable.

For production environments, reconcile credit lines on a case by case basis.

For dev environments, simply delete problematic credit lines:

from django.db.models import F
from corehq.apps.accounting.models import CreditAdjustment, CreditLine
problematic_credit_lines = CreditLine.objects.filter(
    product_type__isnull=False,
    subscription__isnull=False,
).exclude(
    product_type=F('subscription__plan_version__product_rate__product__product_type'),
).exclude(
    balance=0,
).exclude(
    subscription__is_hidden_to_ops=True,
)
CreditAdjustment.objects.filter(credit_line__in=problematic_credit_lines).delete()
CreditAdjustment.objects.filter(related_credit__in=problematic_credit_lines).delete()
problematic_credit_lines.delete()
            """
        )


def confirm_no_mismatched_account_credit_can_be_invoiced_automatically(apps, schema_editor):
    previous_invoicing_date = date(date.today().year, date.today().month, 1)
    subscriptions_in_future_invoicing_periods = apps.get_model('accounting', 'Subscription').objects.exclude(
        date_end__lte=previous_invoicing_date,
    ).exclude(
        is_hidden_to_ops=True,
    )
    if filter(
        lambda sub: apps.get_model('accounting', 'CreditLine').objects.filter(
            account=sub.account,
            product_type__isnull=False,
        ).exclude(
            Q(product_type='') | Q(product_type=sub.plan_version.product_rate.product.product_type)
        ).exclude(
            balance=0
        ).exists(),
        subscriptions_in_future_invoicing_periods
    ):
        raise Exception("""

Running this migration may allow subscriptions in future invoicing periods access to
product credit not originally allocated to the subscription's product type.

For production environments, reconcile credit lines on a case by case basis.

For dev environments, simply delete problematic credit lines:

from datetime import date
from django.db.models import Q
from corehq.apps.accounting.models import CreditAdjustment, CreditLine, Subscription
previous_invoicing_date = date(date.today().year, date.today().month, 1)
subscriptions_in_future_invoicing_periods = Subscription.objects.exclude(
    date_end__lte=previous_invoicing_date,
)
for subscription in subscriptions_in_future_invoicing_periods:
    problematic_credit_lines = CreditLine.objects.filter(
        account=subscription.account,
        product_type__isnull=False,
    ).exclude(
        Q(product_type='') | Q(product_type=subscription.plan_version.product_rate.product.product_type)
    ).exclude(
        balance=0
    )
    CreditAdjustment.objects.filter(credit_line__in=problematic_credit_lines).delete()
    CreditAdjustment.objects.filter(related_credit__in=problematic_credit_lines).delete()
    problematic_credit_lines.delete()
            """
        )


def set_credit_line_product_types_to_any(apps, schema_editor):
    apps.get_model('accounting', 'CreditLine').objects.filter(
        product_type__isnull=False,
    ).exclude(
        product_type=''
    ).update(product_type='')


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0022_bootstrap_prbac_roles'),
    ]

    operations = [
        HqRunPython(confirm_no_mismatched_subscription_credit),
        HqRunPython(confirm_no_mismatched_account_credit_can_be_invoiced_automatically),
        HqRunPython(set_credit_line_product_types_to_any),
        migrations.AlterField(
            model_name='creditline',
            name='product_type',
            field=models.CharField(blank=True, max_length=25, null=True, choices=[(b'', b'')]),
            preserve_default=True,
        ),
    ]
