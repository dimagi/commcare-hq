import json

from corehq.apps.hqwebapp.utils.bootstrap.paths import (
    COREHQ_BASE_DIR,
    get_app_template_folder,
    TRACKED_JS_FOLDERS,
    get_app_static_folder,
)

PATH_TO_STATUS = 'apps/hqwebapp/utils/bootstrap/status'


def get_completed_summary():
    file_path = COREHQ_BASE_DIR / PATH_TO_STATUS / "bootstrap3_to_5_completed.json"
    with open(file_path, 'r') as f:
        return json.loads(f.read())


def get_app_status_summary(app_name):
    return get_completed_summary().get(app_name, {})


def get_completed_status(app_name):
    return get_app_status_summary(app_name).get("is_complete", False)


def _get_full_paths(folder, filenames):
    return [folder / filename for filename in filenames]


def get_completed_templates_for_app(app_name, use_full_paths=True):
    completed_templates = get_app_status_summary(app_name).get("templates", [])
    if use_full_paths:
        completed_templates = _get_full_paths(
            get_app_template_folder(app_name),
            completed_templates
        )
    return completed_templates


def get_completed_javascript_for_app(app_name, use_full_paths=True):
    completed_javascript = []
    app_status_summary = get_app_status_summary(app_name)
    app_static_folder = get_app_static_folder(app_name)
    for folder_name in TRACKED_JS_FOLDERS:
        completed_filenames = app_status_summary.get(folder_name, [])
        if use_full_paths:
            completed_filenames = _get_full_paths(
                app_static_folder / folder_name,
                completed_filenames
            )
        completed_javascript.extend(completed_filenames)
    return completed_javascript
