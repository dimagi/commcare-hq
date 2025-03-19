import json
import re

from corehq.apps.hqwebapp.utils.bootstrap.paths import COREHQ_BASE_DIR

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

PATH_TO_SPEC = 'apps/hqwebapp/utils/bootstrap/spec'
PATH_TO_CHANGES_GUIDE = 'apps/hqwebapp/utils/bootstrap/changes_guide'


def get_spec(spec_name):
    file_path = COREHQ_BASE_DIR / PATH_TO_SPEC / f"{spec_name}.json"
    with open(file_path, 'r') as f:
        return json.loads(f.read())


def _get_direct_css_regex(css_class):
    return r"([\n \"\'}])(" + css_class + r")([\n \"\'{])"


def _get_plugin_regex(js_plugin):
    return r"(\.)(" + js_plugin + r")(\()"


def _get_extension_regex(js_plugin):
    return r"(\$\.fn\.)(" + js_plugin + r")(\.Constructor)"


def _get_path_reference_regex(path_reference):
    return r"([\"\'])(" + path_reference + r")([\"\'])"


def _get_template_reference_regex(tag, reference):
    return r"(\{% " + tag + r" ['\"][\w\/.\-]+\/)(" + reference + r")(\/[\w\/.\-]+['\"]?)"


def _get_javascript_reference_regex(reference):
    return r"(['\"][\w/.\-]+/)(" + reference + r")(/[\w/.\-]+['\"],?)"


def _get_mocha_app_regex(app):
    return r"([ ]+[\"\'])(" + app + r")([\"\'],\n)"


def _get_todo_regex(is_template):
    open_comment = r"\{#" if is_template else r"\/\*"
    close_comment = r"#\}" if is_template else r"\*\/"
    return open_comment + r" todo B5: [\w\/.\-:, ]+" + close_comment


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
    file_path = COREHQ_BASE_DIR / PATH_TO_CHANGES_GUIDE / f"{css_class}.md"
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


def make_select_form_control_renames(line, spec):
    if "<select" in line:
        if re.search(_get_direct_css_regex("form-control"), line):
            return _do_rename(
                line,
                {"form-control": "form-select"},
                _get_direct_css_regex,
                lambda x: r"\1form-select\3"
            )
    return line, []


def make_template_tag_renames(line, spec):
    return _do_rename(
        line,
        spec['template_tag_renames'],
        lambda x: r"(\{% )(" + x + r")( [^%]* %})",
        lambda x: r"\1" + spec['template_tag_renames'][x] + r"\3"
    )


def make_data_attribute_renames(line, spec):
    return _do_rename(
        line,
        spec['data_attribute_renames'],
        lambda x: r"([\n }\"\'])(" + x + r")([\"\']?[=:]\s*[\"\'])",
        lambda x: r"\1" + spec['data_attribute_renames'][x] + r"\3"
    )


def make_javascript_dependency_renames(line, spec):
    return _do_rename(
        line,
        spec['dependency_renames'],
        lambda x: _get_javascript_reference_regex(x),
        lambda x: r"\1" + spec['dependency_renames'][x] + r"\3"
    )


def make_template_dependency_renames(line, spec):
    for tag in spec['template_tags_with_dependencies']:
        final_line, renames = _do_rename(
            line,
            spec['dependency_renames'],
            lambda x: _get_template_reference_regex(tag, x),
            lambda x: r"\1" + spec['dependency_renames'][x] + r"\3"
        )
        if renames:
            return final_line, renames
    return line, []


def add_todo_comments_for_flags(flags, line, is_template):
    if flags:
        line = line.rstrip('\n')
        flag_summary = [f[0] for f in flags]
        open_comment = "{#" if is_template else "/*"
        close_comment = "#}" if is_template else "*/"
        comment = f"{open_comment} todo B5: {', '.join(flag_summary)} {close_comment}\n"

        todo_regex = _get_todo_regex(is_template)
        if re.search(todo_regex, line):
            line = re.sub(
                pattern=todo_regex,
                repl=comment,
                string=line
            )
        else:
            line = f"{line}  {comment}"
    return line


def flag_changed_css_classes(line, spec):
    flags = []
    for css_class in spec['flagged_css_changes']:
        regex = _get_direct_css_regex(css_class)
        if re.search(regex, line):
            flags.append([
                f'css-{css_class}',
                _get_change_guide(f'css-{css_class}')
            ])
    return flags


def flag_changed_javascript_plugins(line, spec):
    flags = []
    for plugin in spec['flagged_js_plugins']:
        plugin_regex = _get_plugin_regex(plugin)
        extension_regex = _get_extension_regex(plugin)
        if re.search(plugin_regex, line) or re.search(extension_regex, line):
            flags.append([
                f'js-{plugin}',
                _get_change_guide(f"js-{plugin}")
            ])
    return flags


def flag_stateful_button_changes_bootstrap5(line):
    flags = []
    regex = r"([\n }])(data-\w*-text)(=[\"\'])"
    if re.search(regex, line):
        flags.append([
            "stateful button",
            "You are using stateful buttons here, "
            "which are no longer supported in Bootstrap 5."
        ])
    return flags


def check_bootstrap3_references_in_template(line, spec):
    issues = []
    for tag in spec['template_tags_with_dependencies']:
        b3_ref_regex = _get_template_reference_regex(tag, 'bootstrap3')
        tag_only_regex = r"(\{% " + tag + r" ['\"][\w/.\-]+)"
        if re.search(b3_ref_regex, line):
            if tag == "extends":
                issues.append("This template extends a bootstrap 3 template.")
            if tag == "static":
                issues.append("This template references a bootstrap 3 static file.")
            if tag == "include":
                issues.append("This template includes a bootstrap 3 template.")
            if tag == "requirejs_main":
                issues.append("This template references a bootstrap 3 requirejs file. "
                             "It should also use requirejs_main_b5 instead of requirejs_main.")
            if tag == "requirejs_main_b5":
                issues.append("This template references a bootstrap 3 requirejs file.")
            if tag == "js_entry_b3":
                issues.append("This template references a bootstrap 3 webpack entry point. "
                             "It should also use js_entry instead of js_entry_b3.")
            if tag == "js_entry":
                issues.append("This template references a bootstrap 3 webpack entry point.")
        elif re.search(tag_only_regex, line):
            if tag == "requirejs_main":
                issues.append("This template should use requirejs_main_b5 instead of requirejs_main.")
            if tag == "js_entry_b3":
                issues.append("This template should use js_entry instead of js_entry_b3.")
    regex = r"(=[\"\'][\w\/]+)(\/bootstrap3\/)"
    if re.search(regex, line):
        issues.append("This template references a bootstrap 3 file.")
    return issues


def check_bootstrap3_references_in_javascript(line):
    issues = []
    regex = _get_javascript_reference_regex('bootstrap3')
    if re.search(regex, line):
        issues.append("This javascript file references a bootstrap 3 file.")
    return issues


def flag_file_inputs(line):
    flags = []
    regex = r"\btype\s*=\s*.file"
    if re.search(regex, line):
        flags.append([
            "css-file-inputs",
            _get_change_guide("css-file-inputs")
        ])
    return flags


def flag_inline_styles(line):
    flags = []
    regex = r"\bstyle\s*=\s*"
    if re.search(regex, line):
        flags.append([
            "inline-style",
            _get_change_guide("inline-style")
        ])
    return flags


def flag_crispy_forms_in_template(line):
    flags = []
    regex = r"\{% crispy"
    if re.search(regex, line):
        flags.append([
            "crispy",
            _get_change_guide("crispy")
        ])
    return flags


def flag_selects_without_form_control(line):
    flags = []
    if "<select" in line:
        if "form-select" not in line and "form-control" not in line:
            flags.append([
                "css-select-form-control",
                _get_change_guide("css-select-form-control")
            ])
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


def update_gruntfile(filedata, mocha_paths):
    mocha_apps = [path.replace('/spec/', '/').removesuffix('/mocha.html')
                  for path in mocha_paths]
    for app in mocha_apps:
        regex = _get_mocha_app_regex(app)
        filedata = re.sub(
            pattern=regex,
            repl=r"\1" + f"{app}/bootstrap3" + r"\3\1" + f"{app}/bootstrap5" + r"\3",
            string=filedata
        )
    return filedata
