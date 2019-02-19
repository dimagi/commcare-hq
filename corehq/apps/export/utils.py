from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.apps.accounting.utils import domain_has_privilege
from corehq.privileges import EXCEL_DASHBOARD, DAILY_SAVED_EXPORT

import six


def is_occurrence_deleted(last_occurrences, app_ids_and_versions):
    is_deleted = True
    for app_id, version in six.iteritems(app_ids_and_versions):
        occurrence = last_occurrences.get(app_id)
        if occurrence is not None and occurrence >= version:
            is_deleted = False
            break
    return is_deleted


def domain_has_excel_dashboard_access(domain):
    return domain_has_privilege(domain, EXCEL_DASHBOARD)


def domain_has_daily_saved_export_access(domain):
    return domain_has_privilege(domain, DAILY_SAVED_EXPORT)
