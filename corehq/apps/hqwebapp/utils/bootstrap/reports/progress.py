import json

from corehq.apps.hqwebapp.utils.bootstrap.paths import COREHQ_BASE_DIR

PATH_TO_PROGRESS_NOTES = 'apps/hqwebapp/utils/bootstrap/reports/progress'


def get_progress_file_path():
    return COREHQ_BASE_DIR / PATH_TO_PROGRESS_NOTES / "bootstrap3_to_5.json"


def get_progress_data():
    with open(get_progress_file_path(), 'r') as f:
        return json.loads(f.read())


def update_progress_data(data):
    for key in data.keys():
        data[key] = sorted(data[key])
    data_string = json.dumps(data, indent=2)
    with open(get_progress_file_path(), "w") as f:
        f.writelines(data_string + '\n')


def _mark_as_complete(item, category):
    progress_data = get_progress_data()
    if item not in progress_data[category]:
        progress_data[category].append(item)
    update_progress_data(progress_data)


def _get_category_list(category):
    progress_data = get_progress_data()
    return progress_data[category]


def mark_report_as_complete(report_name):
    _mark_as_complete(report_name, "reports")


def mark_filter_as_complete(filter_path):
    _mark_as_complete(filter_path, "filters")


def mark_filter_template_as_complete(filter_template):
    _mark_as_complete(filter_template, "filter_templates")


def get_migrated_reports():
    return _get_category_list("reports")


def get_migrated_filters():
    return _get_category_list("filters")


def get_migrated_filter_templates():
    return _get_category_list("filter_templates")
