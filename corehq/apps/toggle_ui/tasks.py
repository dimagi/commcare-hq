import csv
import inspect
from collections import defaultdict
from datetime import datetime

import pytz
from celery.task import task
from couchdbkit import ResourceNotFound
from django.conf import settings

from corehq.apps.domain.calculations import last_form_submission
from corehq.apps.domain.models import Domain
from corehq.apps.toggle_ui.utils import has_dimagi_user, get_subscription_info
from corehq.apps.users.models import CouchUser
from corehq.blobs import get_blob_db, CODES
from corehq.const import USER_DATETIME_FORMAT
from corehq.toggles import (
    NAMESPACE_USER, NAMESPACE_DOMAIN, NAMESPACE_EMAIL_DOMAIN, NAMESPACE_OTHER, all_toggles
)
from corehq.util.files import safe_filename_header, TransientTempfile
from corehq.util.view_utils import absolute_reverse
from couchforms.analytics import domain_has_submission_in_last_30_days
from dimagi.utils.django.email import send_HTML_email
from soil import DownloadBase
from soil.util import expose_blob_download
from toggle.models import Toggle


@task(bind=True)
def generate_toggle_csv_download(self, tag, download_id, username):
    toggles = _get_toggles_with_tag(tag)
    total = _get_toggle_item_count(toggles)
    current_progress = [0]

    def increment_progress():
        current_progress[0] += 1
        DownloadBase.set_progress(self, current_progress[0], total)

    timeout_mins = 24 * 60
    with TransientTempfile() as temp_path:
        _write_toggle_data(temp_path, toggles, increment_progress)

        with open(temp_path, 'rb') as file:
            db = get_blob_db()
            meta = db.put(
                file,
                domain="__system__",
                parent_id="__system__",
                type_code=CODES.tempfile,
                key=download_id,
                timeout=timeout_mins,
            )

    now = datetime.utcnow().strftime("%Y-%m-%d-%H-%M-%S")
    filename = f'{settings.SERVER_ENVIRONMENT}_toggle_export_{now}'
    expose_blob_download(
        download_id,
        expiry=timeout_mins * 60,
        content_disposition=safe_filename_header(filename, ".csv"),
        download_id=download_id,
    )

    user = CouchUser.get_by_username(username)
    if user:
        url = absolute_reverse("retrieve_download", args=[download_id])
        url += "?get_file"
        valid_until = meta.expires_on.replace(tzinfo=pytz.UTC).strftime(USER_DATETIME_FORMAT)
        send_HTML_email("Feature Flag download ready", user.get_email(), html_content=inspect.cleandoc(f"""
        Download URL: {url}
        Download Valid until: {valid_until}
        """))


def _get_toggle_item_count(toggles):
    count = 0
    for toggle in toggles:
        try:
            toggle_doc = Toggle.get(toggle.slug)
        except ResourceNotFound:
            count += 1
            continue

        count += len(set(toggle_doc.enabled_users))
    return count


def _get_toggles_with_tag(tag=None):
    toggles = []
    for toggle in all_toggles():
        if not tag or tag in toggle.tag.name:
            toggles.append(toggle)
    return toggles


def _write_toggle_data(filepath, toggles, increment_progress=None):
    """Generate a CSV file containing data for toggles. One row per enabled toggle item.
    If the toggle is not used a single row will still be included with the basic metadata
    """
    fieldnames = [
        "env", "slug", "label", "tag", "type", "help", "description", "randomness",
        "enabled_for_new_domains_after", "enabled_for_new_users_after", "relevant_to_env",
        "user_count", "domain_count", "email_domain_count", "other_count", "error",
        "item", "item_namespace",
        # user columns
        "user_is_active", "user_is_dimagi", "user_is_mobile", "user_is_superuser", "user_last_login",
        # domain columns
        "domain_is_active", "domain_is_test", "domain_is_snapshot",
        "domain_has_dimagi_user", "domain_last_form_submission", "domain_has_submission_in_last_30_days",
        "domain_subscription_service_type", "domain_subscription_plan"
    ]
    with open(filepath, 'w', encoding='utf8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for toggle in toggles:
            for row in _get_toggle_rows(toggle):
                writer.writerow(row)
                increment_progress and increment_progress()


def _get_toggle_rows(toggle):
    relevant_environments = toggle.relevant_environments
    relevant_to_env = bool(not relevant_environments or settings.SERVER_ENVIRONMENT in relevant_environments)
    toggle_data = {
        "env": settings.SERVER_ENVIRONMENT,
        "label": toggle.label,
        "slug": toggle.slug,
        "tag": toggle.tag.name,
        "type": toggle.__class__.__name__,
        "help": toggle.help_link,
        "description": toggle.description,
        "randomness": getattr(toggle, "randomness", "---"),
        "enabled_for_new_domains_after": toggle.enabled_for_new_domains_after or "---",
        "enabled_for_new_users_after": toggle.enabled_for_new_users_after or "---",
        "relevant_to_env": relevant_to_env,
    }

    try:
        toggle_doc = Toggle.get(toggle.slug)
    except ResourceNotFound:
        return [{**toggle_data, **{
            "user_count": 0,
            "domain_count": 0,
            "email_domain_count": 0,
            "other_count": 0,
        }}]

    enabled_items = toggle_doc.enabled_users
    items_by_ns = defaultdict(set)
    for item in enabled_items:
        namespace = "user"
        if ":" in item:
            namespace, item = item.split(':', 1)
        items_by_ns[namespace].add(item)
    items_by_ns[NAMESPACE_DOMAIN].update(toggle.always_enabled)
    items_by_ns[NAMESPACE_DOMAIN].difference_update(toggle.always_disabled)

    # map 'None' to the user namespace
    namespaces = [NAMESPACE_USER if ns is None else ns for ns in toggle.namespaces]

    def _ns_count(ns):
        return len(items_by_ns[ns]) if ns in namespaces else 0

    toggle_data.update({
        "user_count": _ns_count(NAMESPACE_USER),
        "domain_count": _ns_count(NAMESPACE_DOMAIN),
        "email_domain_count": _ns_count(NAMESPACE_EMAIL_DOMAIN),
        "other_count": _ns_count(NAMESPACE_OTHER),
    })

    if not items_by_ns or not any(items_by_ns.values()):
        return [toggle_data]

    def _item_info(item, ns):
        return {"item": item, "item_namespace": ns}

    rows = []
    for ns in items_by_ns:
        for item in items_by_ns[ns]:
            item_info = _item_info(item, ns)
            ns_info = {}
            if ns == NAMESPACE_DOMAIN:
                ns_info = _get_domain_info(item)
            if ns == NAMESPACE_USER:
                ns_info = _get_user_info(item)
            rows.append({**toggle_data, **item_info, **ns_info})
    return rows


def _get_domain_info(domain):
    domain_obj = Domain.get_by_name(domain)
    if not domain_obj:
        return {"error": "Domain not found"}

    service_type, plan = get_subscription_info(domain)
    return {
        "domain_is_active": domain_obj.is_active,
        "domain_is_test": {"true": "True", "false": "False", "none": "unknown"}[domain_obj.is_test],
        "domain_is_snapshot": domain_obj.is_snapshot,
        "domain_has_dimagi_user": has_dimagi_user(domain),
        "domain_last_form_submission": last_form_submission(domain),
        "domain_has_submission_in_last_30_days": domain_has_submission_in_last_30_days(domain),
        "domain_subscription_service_type": service_type,
        "domain_subscription_plan": plan,
    }


def _get_user_info(username):
    user = CouchUser.get_by_username(username)
    if not user:
        return {"error": "User not found"}

    return {
        "user_is_dimagi": "@dimagi.com" in username,
        "user_is_mobile": "commcarehq.org" in username,
        "user_is_active": user.is_active,
        "user_last_login": user.last_login,
        "user_is_superuser": user.is_superuser,
    }
