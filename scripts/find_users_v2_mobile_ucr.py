
# This script finds all apps across domains that are using v1 and manual references if any
# Steps followed
# 1. Get All domains with mobile ucr flag enabled
# 2. Get all apps for domain with all released versions and mobile ucr versions that are not v2
# 3. For each app build, find no. of reporting modules
# 4. Fpr each app if reporting modules are used,  find commcare:reports fixture and any manual references

# How to run
# Can be run in django shell. Paste the script and execute the function process(as_json_file=True)
# File is stored in home directory of cchq user.

# V1 Examples
# https://staging.commcarehq.org/a/test-commcare-superset/apps/view/f940fcc83bae44b8a0adaf719673fd1e/form/a0f3c5b483c645e78b6f89ee0b3b3c03/source/#form/table_child_count


import json
import re
import traceback
from dataclasses import asdict, dataclass, field
from itertools import chain

from corehq.apps.accounting.models import Subscription
from corehq.apps.app_manager.dbaccessors import get_all_apps, get_apps_in_domain
from corehq.toggles import MOBILE_UCR
from corehq.toggles.shortcuts import find_domains_with_toggle_enabled
from corehq.util.log import with_progress_bar
from dimagi.utils.couch.database import iter_docs
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.util import get_correct_app_class

def set_max_memory(size):    # size (in bytes)
    import resource
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    resource.setrlimit(resource.RLIMIT_AS, (size, hard))


@dataclass
class NonV2Form:
    form_id: str
    form_name: str
    no_of_references: int = 0
    references: list = field(default_factory=list)


@dataclass
class NonV2App:
    app_id: str
    app_name: str
    app_version: str
    mobile_ucr_version: str
    is_released: bool = True
    reporting_modules_count: list = 0
    reports: list = field(default_factory=list)
    non_v2_forms: list[NonV2Form] = field(default_factory=list)


@dataclass
class NonV2MobileUCRReport:
    domain: str
    subscription: str = ''
    apps: list[NonV2App] = field(default_factory=list)

    def flatten(self):
        results = []
        for app in self.apps:
            row = {}
            row["domain"] = self.domain
            row["subscription"] = self.subscription
            # row["apps_count"] = len(self.apps)
            app_data = asdict(app)
            app_data.pop("non_v2_forms")
            row.update(app_data)
            row["forms_count"] = len(app.non_v2_forms)
            if app.non_v2_forms:
                for form in app.non_v2_forms:
                    row_copy = row.copy()
                    row_copy.update(asdict(form))
                    results.append(row_copy)
            else:
                results.append(row)
        return results


def save_in_log(file, data):
    print(data)
    file.write(data+'\n')


def save_as_ndjson(path, data):
    with open(path, 'a') as file:
        print(json.dumps(data, separators=(',', ':')), file=file)


def read_ndjson_file(path):
    with open(path, 'r') as file:
        return [json.loads(l) for l in file.readlines()]


# USER = 'ajeet/local-non-v2-ucr/'
USER = 'cchq'
REPORT_PATH = f'/home/{USER}/non_v2_ucr_report.ndjson'
PROCESSED_DOMAINS_PATH = f'/home/{USER}/processed_domains.ndjson'
PROCESSED_APPS_PATH = f'/home/{USER}/processed_apps.ndjson'
ERRORED_APPS_PATH = f'/home/{USER}/errored_apps.ndjson'
LOG_FILE = f'/home/{USER}/non_v2_ucr_script.log'

V1_FIXTURE_IDENTIFIER = 'src="jr://fixture/commcare:reports'
V1_FIXTURE_PATTERN = r'<.*src="jr://fixture/commcare:reports.*>'
V1_REFERENCES_PATTERN = r"<.*instance\('reports'\)/reports/.*>"
V1_ALL_REFERENCES = f"{V1_FIXTURE_PATTERN}|{V1_REFERENCES_PATTERN}"

skip_domains = []


def get_unprocessed_apps(domain, processed_apps, errored_apps, log_file):
    # Code used from get_all_apps. Uses a custom chunk size and gets standard applications in chunks as well
    saved_app_ids = Application.get_db().view(
        'app_manager/saved_app',
        startkey=[domain],
        endkey=[domain, {}],
        include_docs=False,
        wrapper=lambda row: row['id'],
    )
    app_ids = Application.get_db().view(
        'app_manager/applications',
        startkey=[domain, None],
        endkey=[domain, None, {}],
        include_docs=False,
        wrapper=lambda row: row['id'],
    )
    all_app_ids = list(saved_app_ids)
    all_app_ids.extend(list(app_ids))

    save_in_log(log_file, f"Total Apps found:{len(all_app_ids)}")
    all_app_ids = [app_id for app_id in all_app_ids if app_id not in processed_apps
                   and app_id not in errored_apps]
    save_in_log(log_file, f"Total Apps pending:{len(all_app_ids)}")

    correct_wrap = lambda app_doc: get_correct_app_class(app_doc).wrap(app_doc)
    saved_apps = map(correct_wrap, iter_docs(Application.get_db(), saved_app_ids, chunksize=5))
    return saved_apps


def run(results_as_json_file=False, mobile_ucr_domains=None):
    results = []
    try:
        processed_domains = read_ndjson_file(PROCESSED_DOMAINS_PATH)
    except FileNotFoundError:
        processed_domains = []

    if not mobile_ucr_domains:
        mobile_ucr_domains = find_domains_with_toggle_enabled(MOBILE_UCR)

    log_file = open(LOG_FILE, 'a')

    save_in_log(log_file, f"Number of domains with mobile ucr flag enabled: {len(mobile_ucr_domains)} ")
    for domain in with_progress_bar(mobile_ucr_domains):
        if domain in processed_domains:
            save_in_log(log_file,f"Already processed domain: {domain}")
            continue
        if domain in skip_domains:
            save_in_log(log_file, f"Skipped domain: {domain}")
            continue

        processed_apps = []
        try:
            processed_apps = [app['app_id'] for app in read_ndjson_file(PROCESSED_APPS_PATH)
                              if app['domain'] == domain]
        except FileNotFoundError:
            pass
        errored_apps = []
        try:
            errored_apps = [app['app_id'] for app in read_ndjson_file(ERRORED_APPS_PATH)
                              if app['domain'] == domain]
        except FileNotFoundError:
            pass

        save_in_log(log_file, f"Processing domain: {domain} ...")
        try:
            subscription = Subscription.get_active_subscription_by_domain(domain)
            non_v2_mobile_ucr_report = NonV2MobileUCRReport(domain=domain)
            if subscription:
                non_v2_mobile_ucr_report.subscription = subscription.plan_version.plan.name

            apps = get_unprocessed_apps(domain, processed_apps, errored_apps, log_file)

            for app in apps:
                # App details
                try:
                    if app.is_released and app.mobile_ucr_restore_version != '2.0':
                        save_in_log(log_file, f"Processing App: {domain}: {app.name}: {app.id}")
                        non_v2_app = NonV2App(app.id, app.name, app.version, app.mobile_ucr_restore_version)
                        # Updated to store report app wise
                        non_v2_mobile_ucr_report.apps = [non_v2_app]
                        reporting_modules = list(app.get_report_modules())

                        # Report details
                        if reporting_modules:
                            non_v2_app.reporting_modules_count = len(reporting_modules)
                            for module in reporting_modules:
                                non_v2_app.reports.extend(
                                    [{"config_id": r.config_id, "title": r.title} for r in module.reports]
                                )

                            # Form details
                            for form in app.get_forms():
                                save_in_log(log_file, f"Processing Form: {domain}: {form.name}")
                                if V1_FIXTURE_IDENTIFIER in form.source:
                                    matched_patterns = re.findall(V1_ALL_REFERENCES, form.source)
                                    non_v2_form = NonV2Form(form.id, str(form.name), len(matched_patterns), matched_patterns)
                                    non_v2_app.non_v2_forms.append(non_v2_form)

                        # Save report to ndjson for each app
                        if non_v2_mobile_ucr_report.apps:
                            if results_as_json_file:
                                save_as_ndjson(REPORT_PATH, non_v2_mobile_ucr_report.flatten())
                            else:
                                results.extend(non_v2_mobile_ucr_report.flatten())
                        save_as_ndjson(PROCESSED_APPS_PATH, {'domain': domain, 'app_id': app.id})
                    else:
                        print(f"App {app.id} not released or uses v2 version")
                except Exception as e:
                    save_in_log(log_file, f"Error occurred for {domain}: {str(e)}")
                    save_in_log(log_file, traceback.format_exc())
                    save_as_ndjson(ERRORED_APPS_PATH, {'domain': domain, 'app_id': app.id, 'error': str(e)})
                    continue

            save_as_ndjson(PROCESSED_DOMAINS_PATH, domain)
        except Exception as e:
            save_in_log(log_file, f"Error occurred for {domain}: {str(e)}")
            save_in_log(log_file, traceback.format_exc())
            continue

    log_file.close()
    return results


# Steps to execute
skip_domains = []
# Sets hard limit of RAM to 600 MB
set_max_memory(1024*1024*600)
# MOBILE_UCR_DOMAINS = ['casesearch']
run(results_as_json_file=True)
