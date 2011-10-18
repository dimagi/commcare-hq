from corehq.apps.groups.models import Group
from corehq.apps.reports.display import xmlns_to_name
from corehq.apps.users.models import CommCareUser
from dimagi.utils.couch.database import get_db

def report_context(domain, report_partial=None, title=None, individual=None, case_type=None, group=None, datespan=None):
    context = {
        "domain": domain,
        "report": {
            "name": title
        }
    }
    if report_partial:
        context.update(report_partial=report_partial)
    if individual is not None:
        context.update(
            show_users=True,
            users= user_list(domain),
            individual=individual,
        )
    if group is not None:
        context.update(
            show_groups=True,
            group=group,
            groups=Group.by_domain(domain),

        )
    if case_type is not None:
        case_types = get_case_types(domain, individual)
        if len(case_types) == 1:
            case_type = case_types.items()[0][0]
        open_count, all_count = get_case_counts(domain, individual=individual)
        context.update(
            show_case_types=True,
            case_types=case_types,
            n_all_case_types={'all': all_count, 'open': open_count},
            case_type=case_type,
        )
    if datespan:
        context.update(
            show_dates=True,
            datespan=datespan
        )
    return context

def user_list(domain):
    users = list(CommCareUser.by_domain(domain))
    users.extend(CommCareUser.by_domain(domain, is_active=False))
    users.sort(key=lambda user: (not user.is_active, user.username))
    return users

def form_list(domain):
    view = get_db().view("formtrends/form_duration_by_user",
                         startkey=["xdu", domain, ""],
                         endkey=["xdu", domain, {}],
                         group=True,
                         group_level=3,
                         reduce=True)
    return [{"display": xmlns_to_name(r["key"][2], domain), "xmlns": r["key"][2]} for r in view]

def get_case_types(domain, individual=None):
    case_types = {}
    key = [domain]
    for r in get_db().view('hqcase/all_cases',
        startkey=key,
        endkey=key + [{}],
        group_level=2
    ).all():
        case_type = r['key'][1]
        if case_type:
            open_count, all_count = get_case_counts(domain, case_type, individual)
            case_types[case_type] = {'open': open_count, 'all': all_count}
    return case_types

def get_case_counts(domain, case_type=None, individual=None):
    key = [domain, case_type or {}, individual or {}]
    for view_name in ('hqcase/open_cases', 'hqcase/all_cases'):
        try:
            yield get_db().view(view_name,
                startkey=key,
                endkey=key + [{}],
                group_level=0
            ).one()['value']
        except TypeError:
            yield 0