import json
import re

from pathlib import Path

import corehq

"""These are a set of utilities intended to assist with the migration of Bootstrap 3 to 5.

Template operations supported:
- CSS class renames (including renames involving numbers, eg. col-xs-<num> to col-<num>)
- data attribute renames
- flagging CSS classes with more involved restructuring

Javascript operations supported:
- tbd


Migration Guide References:
https://getbootstrap.com/docs/4.6/migration/
https://getbootstrap.com/docs/5.3/migration/
https://nodebb.org/blog/nodebb-specific-bootstrap-3-to-5-migration-guide/
"""

COREHQ_BASE_DIR = Path(corehq.__file__).resolve().parent
PATH_TO_SPEC = 'apps/hqwebapp/utils/bootstrap/spec'
PATH_TO_CHANGES_GUIDE = 'apps/hqwebapp/utils/bootstrap/changes_guide'


def get_spec(spec_name):
    file_path = COREHQ_BASE_DIR / PATH_TO_SPEC / f"{spec_name}.json"
    with open(file_path, 'r') as f:
        return json.loads(f.read())


def _get_direct_css_regex(css_class):
    return r"([\n \"\'}])(" + css_class + r")([\n \"\'{])"


def _get_plugin_regex(js_plugin):
    return r"(\.)(" + js_plugin + r")(\([\{\"\'])"


def _get_extension_regex(js_plugin):
    return r"(\$\.fn\.)(" + js_plugin + r")(\.Constructor)"


def _get_path_reference_regex(path_reference):
    return r"([\"\'])(" + path_reference + r")([\"\'])"


def _do_rename(line, change_map, regex_fn, replacement_fn):
    renames = []
    for css_class in change_map.keys():
        regex = regex_fn(css_class)
        if re.search(regex, line):
            renames.append(f"renamed {css_class} to {change_map[css_class]}")
            line = re.sub(
                pattern=regex,
                repl=replacement_fn(css_class),
                string=line
            )
    return line, renames


def _get_change_guide(css_class):
    file_path = COREHQ_BASE_DIR / PATH_TO_CHANGES_GUIDE / f"{css_class}.txt"
    with open(file_path, 'r') as f:
        return f.read()


def make_direct_css_renames(line, spec):
    return _do_rename(
        line,
        spec['direct_css_renames'],
        _get_direct_css_regex,
        lambda x: r"\1" + spec['direct_css_renames'][x] + r"\3"
    )


def make_numbered_css_renames(line, spec):
    return _do_rename(
        line,
        spec['numbered_css_renames'],
        lambda x: r"([\n \"\'}])(" + x.replace('<num>', r")(\d*)") + r"([\n \"\'{])",
        lambda x: r"\1" + spec['numbered_css_renames'][x].replace('<num>', '') + r"\3\4"
    )


def make_data_attribute_renames(line, spec):
    return _do_rename(
        line,
        spec['data_attribute_renames'],
        lambda x: r"([\n }])(" + x + r")(=[\"\'])",
        lambda x: r"\1" + spec['data_attribute_renames'][x] + r"\3"
    )


def flag_changed_css_classes(line, spec):
    flags = []
    for css_class in spec['flagged_css_changes']:
        regex = _get_direct_css_regex(css_class)
        if re.search(regex, line):
            flags.append(_get_change_guide(css_class))
    return flags


def flag_changed_javascript_plugins(line, spec):
    flags = []
    for plugin in spec['flagged_js_plugins']:
        plugin_regex = _get_plugin_regex(plugin)
        extension_regex = _get_extension_regex(plugin)
        if re.search(plugin_regex, line) or re.search(extension_regex, line):
            flags.append(_get_change_guide(f"js-{plugin}"))
    return flags


def flag_path_references_to_migrated_javascript_files(line, reference):
    flags = []
    if "/" + reference + "/" in line:
        flags.append(f"Found reference to a migrated file ({reference})")
    return flags


def flag_stateful_button_changes_bootstrap5(line):
    flags = []
    regex = r"([\n }])(data-\w*-text)(=[\"\'])"
    if re.search(regex, line):
        flags.append("You are using stateful buttons here, "
                     "which are no longer supported in Bootstrap 5.")
    return flags


def file_contains_reference_to_path(filedata, path_reference):
    regex = _get_path_reference_regex(path_reference)
    return re.search(regex, filedata) is not None


def replace_path_references(filedata, old_reference, new_reference):
    regex = _get_path_reference_regex(old_reference)
    return re.sub(
        pattern=regex,
        repl=r"\1" + new_reference + r"\3",
        string=filedata
    )
