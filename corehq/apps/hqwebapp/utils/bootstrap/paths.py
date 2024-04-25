from pathlib import Path

import corehq

COREHQ_BASE_DIR = Path(corehq.__file__).resolve().parent
CUSTOM_BASE_DIR = COREHQ_BASE_DIR.parent / "custom"
TRACKED_JS_FOLDERS = ["js", "spec"]
PARENT_PATHS = {
    "corehq": COREHQ_BASE_DIR,
    "custom": CUSTOM_BASE_DIR,
    "motech": COREHQ_BASE_DIR / "motech",
    "casexml": COREHQ_BASE_DIR / "ex-submodules/casexml/apps",
    "ex-submodules": COREHQ_BASE_DIR / "ex-submodules",
}


def get_app_name_and_slug(app_name):
    app_parts = app_name.split(".")
    if len(app_parts) == 2:
        return app_parts[0], app_parts[1]
    return '', app_name


def get_parent_path(app_name):
    slug, app_name = get_app_name_and_slug(app_name)
    return PARENT_PATHS.get(slug, COREHQ_BASE_DIR / "apps")


def get_app_template_folder(app_name):
    parent_path = get_parent_path(app_name)
    _, app_name = get_app_name_and_slug(app_name)
    return parent_path / app_name / "templates" / app_name


def get_app_static_folder(app_name):
    parent_path = get_parent_path(app_name)
    _, app_name = get_app_name_and_slug(app_name)
    return parent_path / app_name / "static" / app_name


def get_short_path(app_name, full_path, is_template):
    parent_path = get_parent_path(app_name)
    _, app_name = get_app_name_and_slug(app_name)
    if is_template:
        replace_path = parent_path / app_name / "templates"
    else:
        replace_path = parent_path / app_name / "static"
    return str(full_path).replace(
        str(replace_path) + '/',
        ''
    )


def get_all_template_paths_for_app(app_name):
    app_template_folder = get_app_template_folder(app_name)
    return [f for f in app_template_folder.glob('**/*') if f.is_file() and f.suffix]


def get_all_javascript_paths_for_app(app_name):
    app_static_folder = get_app_static_folder(app_name)
    return [f for f in app_static_folder.glob('**/*.js') if f.is_file()]


def get_split_paths(paths, split_folder='bootstrap3'):
    split_folder = f'/{split_folder}/'
    return [
        path for path in paths if split_folder in str(path)
    ]


def get_split_folders(paths, include_root=False):
    split_files = get_split_paths(paths)
    split_folders = {
        str(path).split('/bootstrap3/')[0] for path in split_files
    }
    if not include_root:
        split_folders = {
            path.replace(str(COREHQ_BASE_DIR), '') for path in split_folders
        }
    return split_folders
