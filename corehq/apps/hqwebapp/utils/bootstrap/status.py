import json

from corehq.apps.hqwebapp.utils.bootstrap.paths import (
    COREHQ_BASE_DIR,
    get_app_template_folder,
    get_app_static_folder,
)

PATH_TO_STATUS = 'apps/hqwebapp/utils/bootstrap/status'


def get_status_file_path():
    return COREHQ_BASE_DIR / PATH_TO_STATUS / "bootstrap3_to_5.json"


def get_status_data():
    with open(get_status_file_path(), 'r') as f:
        return json.loads(f.read())


def update_completed_summary(summary):
    summary = dict(sorted(summary.items()))
    summary_string = json.dumps(summary, indent=2)
    with open(get_status_file_path(), "w") as f:
        f.writelines(summary_string + '\n')


def apply_app_summary_changes(app_name, app_summary):
    full_summary = get_status_data()
    full_summary[app_name] = app_summary
    update_completed_summary(full_summary)


def get_app_status_summary(app_name):
    return get_status_data().get(app_name, {})


def mark_app_as_in_progress(app_name):
    app_summary = get_app_status_summary(app_name)
    app_summary["in_progress"] = True
    apply_app_summary_changes(app_name, app_summary)


def is_app_in_progress(app_name):
    return get_app_status_summary(app_name).get("in_progress", False)


def get_apps_completed_or_in_progress():
    return get_status_data().keys()


def mark_app_as_complete(app_name):
    app_summary = get_app_status_summary(app_name)
    if "in_progress" in app_summary:
        del app_summary["in_progress"]
    app_summary["is_complete"] = True
    apply_app_summary_changes(app_name, app_summary)


def is_app_completed(app_name):
    return get_app_status_summary(app_name).get("is_complete", False)


def mark_template_as_complete(app_name, template_short_path):
    _mark_file_as_complete(app_name, template_short_path, "templates")


def mark_javascript_as_complete(app_name, js_short_path):
    _mark_file_as_complete(app_name, js_short_path, "javascript")


def _mark_file_as_complete(app_name, short_path, file_type):
    app_summary = get_app_status_summary(app_name)
    app_summary.setdefault(file_type, []).append(
        short_path.removeprefix(f"{app_name}/")
    )
    app_summary[file_type] = sorted(app_summary[file_type])
    apply_app_summary_changes(app_name, app_summary)


def get_completed_templates_for_app(app_name, use_full_paths=True):
    return _get_completed_files_for_app(
        app_name, "templates", get_app_template_folder(app_name), use_full_paths
    )


def get_completed_javascript_for_app(app_name, use_full_paths=True):
    return _get_completed_files_for_app(
        app_name, "javascript", get_app_static_folder(app_name), use_full_paths
    )


def _get_completed_files_for_app(app_name, file_type, folder, use_full_paths):
    completed_files = get_app_status_summary(app_name).get(file_type, [])
    if use_full_paths:
        completed_files = _get_full_paths(
            folder,
            completed_files
        )
    return completed_files


def _get_full_paths(folder, filenames):
    return [folder / filename for filename in filenames]
