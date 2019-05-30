from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import

from django.utils.translation import ugettext_lazy as _

from .schema import LimitType

UNITS = {
    'rows',
    'cells',
}

TAGS = {
    'feature:lookup_tables',
}

LIMIT_TYPES = [
    LimitType(
        name='max_rows_per_fixture',
        default=50 * 1000,
        unit='rows',
        description=_("The maximum number of rows allowed per fixture in this project"),
        descriptions_of_impact=[
            _("Uploading a lookup table of more than this number of rows "
              "will result in an error that references this limit."),
            _("Any operation that would result in a lookup table"
              "having more than this number of rows "
              "will result in an error that references this limit."),
            _("Existing lookup tables over this number of rows will come with a warning "
              "that references this limit and cites the limitations to editing."),
        ],
        tags={'feature:lookup_tables'},
    ),
    LimitType(
        name='max_cells_per_fixture',
        default=250 * 1000,
        unit='cells',
        description=_("The maximum number of rows allowed per lookup table in this project"),
        descriptions_of_impact=[
            _("Uploading a lookup table of more than this number of cells "
              "will result in an error that references this limit."),
            _("Any operation that would result in a lookup table"
              "having more than this number of cells "
              "will result in an error that references this limit."),
            _("Existing lookup tables over this number of cells will come with a warning "
              "that references this limit and cites the limitations to editing."),
        ],
        tags={'feature:lookup_tables'},
    ),
    LimitType(
        name='max_total_fixture_rows',
        default=50 * 1000,
        unit='rows',
        description=_("The maximum number of total lookup table rows allowed in this project"),
        descriptions_of_impact=[
            _("Any operation that would result in the project having more than "
              "this number of lookup table rows "
              "will result in an error that references this limit."),
            _("If the project's total lookup table rows are over this limit "
              "the lookup table UI will display "
              "a warning that references this limit and cites the limitations to editing."),
        ],
        tags={'feature:lookup_tables'},
    ),
    LimitType(
        name='max_total_fixture_cells',
        default=250 * 1000,
        unit='cells',
        description=_("The maximum number of total lookup table cells allowed in this project"),
        descriptions_of_impact=[
            _("Any operation that would result in the project having more than "
              "this number of lookup table cells "
              "will result in an error that references this limit."),
            _("If the project's total lookup table cells are over this limit "
              "the lookup table UI will display "
              "a warning that references this limit and cites the limitations to editing."),
        ],
        tags={'feature:lookup_tables'},
    ),
]
