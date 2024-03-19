from pathlib import Path

import corehq

COREHQ_BASE_DIR = Path(corehq.__file__).resolve().parent
TRACKED_JS_FOLDERS = ["js", "spec"]


def get_app_template_folder(app_name):
    return COREHQ_BASE_DIR / "apps" / app_name / "templates" / app_name


def get_app_static_folder(app_name):
    return COREHQ_BASE_DIR / "apps" / app_name / "static" / app_name


def get_short_path(app_name, full_path, is_template):
    if is_template:
        replace_path = COREHQ_BASE_DIR / "apps" / app_name / "templates"
    else:
        replace_path = COREHQ_BASE_DIR / "apps" / app_name / "static"
    return str(full_path).replace(
        str(replace_path) + '/',
        ''
    )


def get_all_template_paths_for_app(app_name):
    app_template_folder = get_app_template_folder(app_name)
    return [f for f in app_template_folder.glob('**/*') if f.is_file()]


def get_all_javascript_paths_for_app(app_name):
    app_static_folder = get_app_static_folder(app_name)
    return [f for f in app_static_folder.glob('**/*.js') if f.is_file()]


def get_split_folders(paths, include_root=False):
    split_files = [
        path for path in paths if '/bootstrap3/' in str(path)
    ]
    split_folders = {
        str(path).split('/bootstrap3/')[0] for path in split_files
    }
    if not include_root:
        split_folders = {
            path.replace(str(COREHQ_BASE_DIR), '') for path in split_folders
        }
    return split_folders
