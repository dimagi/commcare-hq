# This script updates the latest versions of all apps across domains that are using v1 with no manual references
# Steps followed
# 1. Get All domains with mobile ucr flag enabled
# 2. Get all apps for domain with latest released versions and mobile ucr versions that are not v2
# 3. For each app, if it contains no V1 UCR references, update the version to 2

# How to run
# Can be run in django shell. Paste the script and execute the function process()
# File is stored in home directory of cchq user.

# V1 Examples
# https://staging.commcarehq.org/a/test-commcare-superset/apps/view/f940fcc83bae44b8a0adaf719673fd1e/form/a0f3c5b483c645e78b6f89ee0b3b3c03/source/#form/table_child_count


import json
import re
import traceback

from corehq.apps.app_manager.dbaccessors import (
    get_latest_app_ids_and_versions,
    get_apps_by_id,
)
from corehq.apps.app_manager.const import MOBILE_UCR_VERSION_2
from corehq.toggles import MOBILE_UCR
from corehq.toggles.shortcuts import find_domains_with_toggle_enabled
from corehq.util.log import with_progress_bar


def save_in_log(file, data):
    print(data)
    file.write(data + '\n')


def save_as_ndjson(path, data):
    with open(path, 'a') as file:
        print(json.dumps(data, separators=(',', ':')), file=file)


def read_ndjson_file(path):
    with open(path, 'r') as file:
        return [json.loads(line) for line in file.readlines()]


def has_non_v2_form(domain, app, log_file):
    for form in app.get_forms():
        save_in_log(log_file, f"Processing Form: {domain}: {form.name}")
        # The second condition should always be False if the first one is
        # but just as a precaution we check for it
        if V1_FIXTURE_IDENTIFIER in form.source or re.findall(V1_ALL_REFERENCES, form.source):
            save_in_log(log_file, f"App Contains V1 Refs: {domain}: {app.name}")
            return True
    return False


def update_app(domain, app, log_file):
    save_in_log(log_file, f"Updating App: {domain}: {app.name}: {app.id}")
    app.mobile_ucr_restore_version = MOBILE_UCR_VERSION_2
    app.save()


PROCESSED_DOMAINS_PATH = '/home/zandre/cchq/updated_domains.ndjson'
LOG_FILE = '/home/zandre/cchq/update_to_v2_ucr_script.log'

V1_FIXTURE_IDENTIFIER = 'src="jr://fixture/commcare:reports'
V1_FIXTURE_PATTERN = r'<.*src="jr://fixture/commcare:reports.*>'
V1_REFERENCES_PATTERN = r"<.*instance\('reports'\)/reports/.*>"
V1_ALL_REFERENCES = f"{V1_FIXTURE_PATTERN}|{V1_REFERENCES_PATTERN}"


skip_domains = []


def process():
    try:
        processed_domains = read_ndjson_file(PROCESSED_DOMAINS_PATH)
    except FileNotFoundError:
        processed_domains = []

    mobile_ucr_domains = find_domains_with_toggle_enabled(MOBILE_UCR)

    log_file = open(LOG_FILE, 'a')

    save_in_log(log_file, f"Number of domains with mobile ucr flag enabled: {len(mobile_ucr_domains)} ")

    for domain in with_progress_bar(mobile_ucr_domains):
        if domain in processed_domains:
            save_in_log(log_file, f"Already processed domain: {domain}")
            continue
        if domain in skip_domains:
            save_in_log(log_file, f"Skipped domain: {domain}")
            continue

        save_in_log(log_file, f"Processing domain: {domain} ...")
        app_ids = list(get_latest_app_ids_and_versions(domain))
        apps = get_apps_by_id(domain, app_ids)
        for app in apps:
            try:
                # Don't look at app.is_released since the latest version might not be released yet
                if app.mobile_ucr_restore_version != '2.0':
                    save_in_log(log_file, f"Processing App: {domain}: {app.name}: {app.id}")
                    if not has_non_v2_form(domain, app, log_file):
                        update_app(domain, app, log_file)
                    else:
                        save_in_log(
                            log_file,
                            f"App contains V1 references and couldn't updated: {domain}: {app.name}: {app.id}",
                        )
            except Exception as e:
                save_in_log(log_file, f"Error occurred for {domain}: {str(e)}")
                save_in_log(log_file, traceback.format_exc())
                continue
        save_as_ndjson(PROCESSED_DOMAINS_PATH, domain)

    log_file.close()
