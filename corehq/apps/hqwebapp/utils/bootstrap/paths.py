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
