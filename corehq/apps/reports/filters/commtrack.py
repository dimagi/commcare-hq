from django.utils.translation import ugettext_lazy, ugettext_noop

from corehq.apps.programs.models import Program
from corehq.apps.reports.filters.base import (
    BaseSingleOptionFilter,
    CheckboxFilter,
)


class AdvancedColumns(CheckboxFilter):
    label = ugettext_lazy("Show advanced columns")
    slug = "advanced_columns"


class ProgramFilter(BaseSingleOptionFilter):
    slug = "program"
    label = ugettext_noop("Program")
    default_text = ugettext_lazy("All")

    @property
    def options(self):
        programs = Program.by_domain(self.domain)
        return [(program.get_id, program.name) for program in programs]
