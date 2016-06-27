# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from datetime import date, timedelta

from django.db import migrations

from dimagi.utils.couch.database import iter_docs

from corehq.apps.accounting.tasks import ensure_explicit_community_subscription
from corehq.apps.accounting.utils import log_accounting_error
from corehq.apps.domain.models import Domain
from corehq.sql_db.operations import HqRunPython


def _assign_explicit_community_subscriptions(apps, schema_editor):
    today = date.today()
    all_domain_ids = [d['id'] for d in Domain.get_all(include_docs=False)]
    for domain_doc in iter_docs(Domain.get_db(), all_domain_ids):
        domain_name = domain_doc['name']
        from_date = date(today.year, today.month, 1)
        try:
            while from_date <= today:
                ensure_explicit_community_subscription(domain_name, from_date)
                from_date += timedelta(days=1)
        except Exception as e:
            log_accounting_error(
                "During community subscription assignment for domain %s: %s"
                % (domain_name, e.message)
            )


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0036_subscription_skip_invoicing_if_no_feature_charges'),
    ]

    operations = [
        HqRunPython(_assign_explicit_community_subscriptions),

    ]
