from corehq.apps.reports import util
from corehq.apps.reports.custom import ReportField
from corehq.apps.groups.models import Group
from corehq.apps.reports.models import HQUserType
from dimagi.utils.couch.database import get_db

class GroupField(ReportField):
    slug = "group"
    template = "reports/partials/fields/select_group.html"

    def update_context(self):
        group = self.request.GET.get('group', '')
        groups = Group.by_domain(self.domain)
        if group:
            group = Group.get(group)
        self.context['group'] = group
        self.context['groups'] = groups

class FilterUsersField(ReportField):
    slug = "ufilter"
    template = "reports/partials/fields/filter_users.html"

    def update_context(self):
        toggle, show_filter = self.get_user_filter(self.request)
        self.context['show_user_filter'] = show_filter
        self.context['toggle_users'] = toggle

    @classmethod
    def get_user_filter(cls, request):
        ufilter = group = individual = None
        try:
            ufilter = request.GET.getlist('ufilter')
            group = request.GET.get('group', '')
            individual = request.GET.get('individual', '')
        except KeyError:
            pass
        show_filter = True
        toggle = HQUserType.use_defaults()
        if ufilter and not (group or individual):
            toggle = HQUserType.use_filter(ufilter)
        elif group or individual:
            show_filter = False
        return toggle, show_filter

class CaseTypeField(ReportField):
    slug = "case_type"
    template = "reports/partials/fields/case_type.html"

    def update_context(self):
        individual = self.request.GET.get('individual', '')
        group = self.request.GET.get('group', '')

        if individual:
            user_ids = [individual]
        elif group is not None:
            _, user_ids = util.get_group_params(self.domain, group=group, user_id_only=True)
        else:
            user_ids = None

        case_types = self.get_case_types(self.domain, user_ids)
        if len(case_types) == 1:
            case_type = case_types.items()[0][0]
        else:
            case_type = self.request.GET.get('case_type', '')

        open_count, all_count = self.get_case_counts(self.domain, user_ids=user_ids)
        self.context['case_types'] = case_types
        self.context['case_type'] = case_type
        self.context['all_cases_count'] = {'all': all_count, 'open': open_count}

    @classmethod
    def get_case_types(cls, domain, user_ids=None):
        case_types = {}
        key = [domain]
        for r in get_db().view('hqcase/all_cases',
            startkey=key,
            endkey=key + [{}],
            group_level=2
        ).all():
            case_type = r['key'][1]
            if case_type:
                open_count, all_count = cls.get_case_counts(domain, case_type, user_ids)
                case_types[case_type] = {'open': open_count, 'all': all_count}
        return case_types

    @classmethod
    def get_case_counts(cls, domain, case_type=None, user_ids=None):
        user_ids = user_ids or [{}]
        for view_name in ('hqcase/open_cases', 'hqcase/all_cases'):
            def individual_counts():
                for user_id in user_ids:
                    key = [domain, case_type or {}, user_id]
                    try:
                        yield get_db().view(view_name,
                            startkey=key,
                            endkey=key + [{}],
                            group_level=0
                        ).one()['value']
                    except TypeError:
                        yield 0
            yield sum(individual_counts())
