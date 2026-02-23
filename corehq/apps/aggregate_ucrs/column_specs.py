from django.utils.translation import gettext_lazy as _

from corehq.apps.userreports import const

PRIMARY_COLUMN_TYPE_REFERENCE = 'reference'
PRIMARY_COLUMN_TYPE_CONSTANT = 'constant'
PRIMARY_COLUMN_TYPE_SQL = 'sql_statement'
PRIMARY_COLUMN_TYPE_CHOICES = (
    (PRIMARY_COLUMN_TYPE_REFERENCE, _('Reference')),
    (PRIMARY_COLUMN_TYPE_CONSTANT, _('Constant')),
    (PRIMARY_COLUMN_TYPE_SQL, _('SQL Statement')),
)

SECONDARY_COLUMN_TYPE_CHOICES = (
    (const.AGGGREGATION_TYPE_SUM, _('Sum')),
    (const.AGGGREGATION_TYPE_MIN, _('Min')),
    (const.AGGGREGATION_TYPE_MAX, _('Max')),
    (const.AGGGREGATION_TYPE_AVG, _('Average')),
    (const.AGGGREGATION_TYPE_COUNT, _('Count')),
    (const.AGGGREGATION_TYPE_COUNT_UNIQUE, _('Count Unique Values')),
    (const.AGGGREGATION_TYPE_NONZERO_SUM, _('Has a nonzero sum (1 if sum is nonzero else 0).')),
)
