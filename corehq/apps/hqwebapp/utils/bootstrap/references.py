from corehq.apps.hqwebapp.utils.bootstrap.changes import (
    file_contains_reference_to_path,
    replace_path_references,
)
from corehq.apps.hqwebapp.utils.bootstrap.paths import COREHQ_BASE_DIR, CUSTOM_BASE_DIR, PARENT_PATHS


def update_and_get_references(app_name, old_reference, new_reference, is_template=True):
    if app_name == "vellum" and old_reference.endswith(".html"):
        old_reference = f"vellum/templates/{old_reference}"
        new_reference = f"vellum/templates/{new_reference}"

    references = []
    for file_path, filedata in get_references_data(app_name, old_reference, is_template):
        references.append(str(file_path))
        with open(file_path, 'w') as file:
            use_bootstrap5_reference = "/bootstrap5/" in str(file_path)
            bootstrap5_reference = new_reference.replace("/bootstrap3/", "/bootstrap5/")
            file.write(replace_path_references(
                filedata,
                old_reference,
                bootstrap5_reference if use_bootstrap5_reference else new_reference
            ))
    return references


def get_requirejs_reference(short_path):
    return short_path.replace('.js', '')


def get_file_types(app_name, is_template=True):
    if app_name == "vellum":
        return ["**/*.md", "**/*.html", "**/*.js"]
    file_types = ["**/*.py", "**/*.html", "**/*.md"]
    if not is_template:
        file_types.append("**/*.js")
    return file_types


def get_references_data(app_name, reference, is_template=True):
    for file_type in get_file_types(app_name, is_template):
        for directory in _get_reference_directories_for_app(app_name):
            for file_path in directory.glob(file_type):
                if not file_path.is_file():
                    continue
                with open(file_path, 'r') as file:
                    filedata = file.read()
                if file_contains_reference_to_path(filedata, reference):
                    yield file_path, filedata


def _get_reference_directories_for_app(app_name):
    if app_name == "vellum":
        return [PARENT_PATHS.get(app_name)]
    return [COREHQ_BASE_DIR, CUSTOM_BASE_DIR]


def get_references(app_name, reference, is_template=True):
    references = []
    for file_path, filedata in get_references_data(app_name, reference, is_template):
        references.append(str(file_path))
    return references
