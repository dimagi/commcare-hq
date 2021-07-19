from couchexport.writers import Excel2007ExportWriter
from django.utils.translation import ugettext as _
from io import BytesIO
from corehq.toggles import all_toggles

from corehq.apps.accounting.models import Subscription
from corehq.apps.es import UserES
from corehq.util.quickcache import quickcache


def find_static_toggle(slug):
    for toggle in all_toggles():
        if toggle.slug == slug:
            return toggle


def get_flags_attachment_file(tag=None):
    """
    This function returns an excel file which contains information regarding
    the feature flags filtered by the 'tag' argument. For 'tag' = None, all
    flags will be returned.

    The excel file has the following format:
    Each feature flag is represented as a different sheet in the file. For each
    feature flag sheet, the top of the file specifies basic information regarding
    the feature flag, i.e. Label, Slug, Tag, etc.

    The rest of the sheet shows all the domains which has the specific feature flag
    enabled, along with some additional information regarding each domain.
    """

    flags = get_feature_flags(tag)
    headers_table, sheets = parse_flags_to_file_info(flags)

    with Excel2007ExportWriter() as writer:
        outfile = BytesIO()
        writer.open(header_table=headers_table, file=outfile)
        writer.write(list(sheets.items()))

    return outfile


def get_feature_flags(tag=None):
    flags = []
    for toggle in all_toggles():
        if not tag or tag in toggle.tag.name:
            flags.append(toggle)
    return flags


def parse_flags_to_file_info(toggles):
    file_headers = []
    sheets = {}

    toggle_headers = [(
        _("Label"),
        _("Slug"),
        _("Tag"),
        _("Documention link"),
        _("Description")
    )]

    sheet_data_header_row = [
        _("Domain"),
        _("Service Type"),
        _("Plan"),
        _("Has Dimagi User"),
    ]

    for toggle in toggles:
        file_headers.append((toggle.slug, toggle_headers))

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
        sheet_rows.extend(_get_toggle_data_rows(toggle))
        sheets[toggle.slug] = sheet_rows

    return file_headers, sheets


def _get_toggle_data_rows(toggle_):
    rows = []

    for domain in toggle_.get_enabled_domains():
        service_type, plan = get_subscription_info(domain)

        data_row = [
            domain,
            service_type,
            plan,
            has_dimagi_user(domain),
        ]
        rows.append(data_row)

    return rows


@quickcache(['domain'], timeout=60 * 10)
def get_subscription_info(domain):
    subscription = Subscription.get_active_subscription_by_domain(domain)
    if subscription:
        return subscription.service_type, subscription.plan_version.plan.name
    return None, None


@quickcache(['domain'], timeout=60 * 10)
def has_dimagi_user(domain):
    return UserES().web_users().domain(domain).search_string_query('@dimagi.com').count()
