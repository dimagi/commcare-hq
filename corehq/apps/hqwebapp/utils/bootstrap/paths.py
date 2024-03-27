from pathlib import Path

import corehq

COREHQ_BASE_DIR = Path(corehq.__file__).resolve().parent


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


def get_migrated_folders(paths, include_root=False):
    migrated_files = [
        path for path in paths if '/bootstrap3/' in str(path)
    ]
    migrated_folders = {
        str(path).split('/bootstrap3/')[0] for path in migrated_files
    }
    if not include_root:
        migrated_folders = {
            path.replace(str(COREHQ_BASE_DIR), '') for path in migrated_folders
        }
    return migrated_folders
