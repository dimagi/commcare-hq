from casexml.apps.case.models import CommCareCase
from corehq.apps.reports.dont_use.fields import ReportSelectField
from corehq.apps.reports.filters.users import SelectCaseOwnerFilter
from django.utils.translation import ugettext_noop
from corehq.apps.groups.models import Group
from django.utils.translation import ugettext as _


class SelectBlockField(ReportSelectField):
    slug = "block"
    name = ugettext_noop("Name of the Block")
    cssId = "opened_closed"
    cssClasses = "span3"

    def update_params(self):
        blocks = set(self.get_blocks(self.domain))
        block = self.request.GET.get(self.slug, '')

        self.selected = block
        self.options = [dict(val=block_item, text="%s" % block_item) for block_item in blocks]
        self.default_option = _("Select Block")

    @classmethod
    def get_blocks(cls, domain):
        key = [domain]
        for r in CommCareCase.get_db().view('crs_reports/field_block',
                      startkey=key,
                      endkey=key + [{}],
                      group_level=3).all():
            _, _, block_name = r['key']
            if block_name:
                yield block_name


class SelectSubCenterField(ReportSelectField):
    slug = "sub_center"
    name = ugettext_noop("Sub Center")
    cssId = "opened_closed"
    cssClasses = "span3"
    default_option = "Select Sub Center"
    options = []


class SelectASHAField(SelectCaseOwnerFilter):
    name = ugettext_noop("ASHA")
    default_option = ugettext_noop("Type ASHA name")
