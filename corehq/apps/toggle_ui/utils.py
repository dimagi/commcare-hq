from couchexport.writers import Excel2007ExportWriter
from django.utils.translation import ugettext as _
from io import BytesIO
from corehq.toggles import all_toggles

from corehq.apps.accounting.models import Subscription
from corehq.apps.es import UserES


def find_static_toggle(slug):
    for toggle in all_toggles():
        if toggle.slug == slug:
            return toggle


def get_subscription_info(domain):
    subscription = Subscription.get_active_subscription_by_domain(domain)
    if subscription:
        return subscription.service_type, subscription.plan_version.plan.name
    else:
        return None, None


def has_dimagi_user(domain):
    return UserES().web_users().domain(domain).search_string_query('@dimagi.com').count()


def parse_flags_to_file_info(toggles):
    def get_header(slug):
        return (slug, [(
            _("Label"),
            _("Slug"),
            _("Tag"),
            _("Documention link"),
            _("Description")
        )])

    def get_toggle_data_rows(toggle_):
        rows = []

        for domain in toggle_.get_enabled_domains():
            (service_type, plan) = get_subscription_info(domain)

            data_row = [
                domain,
                service_type,
                plan,
                has_dimagi_user(domain),
            ]
            rows.append(data_row)

        return rows

    file_headers = []
    sheets = {}

    sheet_data_header_row = [
        _("Domain"),
        _("Service Type"),
        _("Plan"),
        _("Has Dimagi User"),
    ]

    for toggle in toggles:
        file_headers.append(get_header(toggle.slug))

        sheet_header_row_info = [
            toggle.label or '',
            toggle.slug,
            toggle.tag.name,
            toggle.help_link or '',
            toggle.description or '',
        ]

        sheet_rows = [
            sheet_header_row_info,
            [],  # leaves empty row
            sheet_data_header_row,
        ]
        sheet_rows.extend(get_toggle_data_rows(toggle))
        sheets[toggle.slug] = sheet_rows

    return file_headers, sheets


def get_flags_with_tag(tag):
    flags = []
    for toggle in all_toggles():
        if tag == 'all' or tag in toggle.tag.name:
            flags.append(toggle)
    return flags


def get_flags_attachment_file(tag='all'):
    flags = get_flags_with_tag(tag)
    (headers_table, sheets) = parse_flags_to_file_info(flags)

    writer = Excel2007ExportWriter()
    outfile = BytesIO()
    writer.open(header_table=headers_table, file=outfile)

    for sheet_name, sheet_rows in sheets.items():
        writer.write([(sheet_name, sheet_rows)])

    writer.close()
    return outfile
