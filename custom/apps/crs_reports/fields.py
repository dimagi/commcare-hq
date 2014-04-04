from corehq.apps.reports.dont_use.fields import ReportSelectField, SelectCaseOwnerField
from django.utils.translation import ugettext_noop
from corehq.apps.groups.models import Group
from dimagi.utils.couch.database import get_db
from django.utils.translation import ugettext as _


class SelectPNCStatusField(ReportSelectField):
    slug = "PNC_status"
    name = ugettext_noop("Status")
    cssId = "opened_closed"
    cssClasses = "span3"
    default_option = "Select PNC Status"
    options = [dict(val="On Time", text=ugettext_noop("On time")),
               dict(val="Late", text=ugettext_noop("Late"))]


class SelectBlockField(ReportSelectField):
    slug = "block"
    name = ugettext_noop("Block")
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
        for r in get_db().view('crs_reports/field_block',
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


class SelectASHAField(SelectCaseOwnerField):
    name = ugettext_noop("ASHA")
    default_option = ugettext_noop("Type ASHA name")

    def update_params(self):
        case_sharing_groups = Group.get_case_sharing_groups(self.domain)
        self.context["groups"] = [dict(group_id=group._id, name=group.name) for group in case_sharing_groups]
