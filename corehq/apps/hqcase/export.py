from corehq.apps.hqcase.dbaccessors import get_case_properties
from corehq.apps.users.cases import get_owner_id
from soil import DownloadBase


def export_cases(domain, cases, workbook, filter_group=None, users=None, all_groups=None, process=None):
    by_user_id = dict([(user.user_id, user) for user in users]) if users else {}
    by_group_id = dict([(g.get_id, g) for g in all_groups]) if all_groups else {}
    if filter_group:
        owner_ids = set(by_user_id.keys())
        owner_ids.add(filter_group.get_id)

    case_static_keys = (
        "case_id",
        "username",
        "user_id",
        "owner_id",
        "owner_name",
        "type",
        "name",
        "opened_on",
        "modified_on",
        "closed",
        "closed_on",
        "domain",
        "external_id",
    )
    referral_keys = (
        "case_id",
        'referral_id',
        "type",
        "opened_on",
        "modified_on",
        "followup_on",
        "closed",
    )
    case_dynamic_keys = get_case_properties(domain)
    case_rows = []

    def render_case_attr(case, key):
        attr = getattr(case, key)
        if isinstance (attr, dict):
            return attr.get('#text', '')
        else:
            return attr

    num_cases = len(cases)

    def get_matching_owner(case):
        if by_user_id:
            if case.user_id in by_user_id:
                return case.user_id
            elif get_owner_id(case) in by_user_id:
                return get_owner_id(case)
        else:
            return get_owner_id(case)

    def might_be_relevant(case):
        return not filter_group or get_owner_id(case) in owner_ids

    for i, case in enumerate(cases):
        if process:
            DownloadBase.set_progress(process, i, num_cases)
        if might_be_relevant(case):
            matching_owner = get_matching_owner(case)
            case_row = {'dynamic_properties': {}}
            for key in case_static_keys:
                if key == 'username':
                    try:
                        case_row[key] = by_user_id[matching_owner].raw_username
                    except (TypeError, KeyError):
                        case_row[key] = ''
                elif key == 'owner_name':
                    if users and case.owner_id in by_user_id:
                        case_row[key] = by_user_id[case.owner_id].full_name
                    elif case.owner_id in by_group_id:
                        case_row[key] = by_group_id[case.owner_id].name
                    else:
                        case_row[key] = ''
                else:
                    case_row[key] = getattr(case, key)
            for key in case.dynamic_properties():
                case_row['dynamic_properties'][key] = render_case_attr(case, key)
            case_rows.append(case_row)

    def format_dynamic_key(key):
        return "d.{key}".format(key=key)

    def tidy_up_case_row(case_row):
        row = dict([(key, case_row[key]) for key in case_static_keys])
        for key in case_dynamic_keys:
            row[format_dynamic_key(key)] = case_row['dynamic_properties'].get(key, workbook.undefined)
        return row

    case_headers = list(case_static_keys)
    case_headers.extend([format_dynamic_key(key) for key in case_dynamic_keys])
    workbook.open("Cases", case_headers)
    for case_row in case_rows:
        workbook.write_row("Cases", tidy_up_case_row(case_row))

    return workbook
