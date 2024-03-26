from testil import eq
from corehq.apps.hqwebapp.utils.bootstrap.changes import (
    get_spec,
    make_direct_css_renames,
    make_numbered_css_renames,
    make_data_attribute_renames,
    flag_changed_css_classes,
    flag_stateful_button_changes_bootstrap5,
    flag_changed_javascript_plugins,
    flag_path_references_to_split_javascript_files,
    file_contains_reference_to_path,
    replace_path_references,
    flag_bootstrap3_references_in_template,
)


def test_make_direct_css_renames_bootstrap5():
    line = """        <button class="btn-xs btn btn-default context-right btn-xs" id="prepaid-snooze"></button>\n"""
    final_line, renames = make_direct_css_renames(
        line, get_spec('bootstrap_3_to_5')
    )
    eq(final_line, '        <button class="btn-sm btn btn-outline-primary '
                   'context-right btn-sm" id="prepaid-snooze"></button>\n')
    eq(renames, ['renamed btn-default to btn-outline-primary', 'renamed btn-xs to btn-sm'])


def test_make_numbered_css_renames_bootstrap5():
    line = """        <div class="col-xs-6">\n"""
    final_line, renames = make_numbered_css_renames(
        line, get_spec('bootstrap_3_to_5')
    )
    eq(final_line, """        <div class="col-sm-6">\n""")
    eq(renames, ['renamed col-xs-<num> to col-sm-<num>'])


def test_make_data_attribute_renames_bootstrap5():
    line = """        <button data-toggle="modal">\n"""
    final_line, renames = make_data_attribute_renames(
        line, get_spec('bootstrap_3_to_5')
    )
    eq(final_line, """        <button data-bs-toggle="modal">\n""")
    eq(renames, ['renamed data-toggle to data-bs-toggle'])


def test_flag_changed_css_classes_bootstrap5():
    line = """        <dl class="dl-horizontal">\n"""
    flags = flag_changed_css_classes(
        line, get_spec('bootstrap_3_to_5')
    )
    eq(flags, ['`dl-horizontal` has been dropped.\nInstead, use `.row` on `<dl>` and use grid column classes '
               '(or mixins) on its `<dt>` and `<dd>` children.\n\nAn EXAMPLE for how to apply this change is '
               'provided below.\nPlease see docs for further details.\n\nPreviously:\n```\n<dl class='
               '"dl-horizontal">\n    <dt>foo</dt>\n    <dd>foo</dd>\n</dl>\n```\n\nNow:\n```\n<dl class='
               '"row">\n    <dt class="col-3">foo</dt>\n    <dd class="col-9">foo</dd>\n</dl>\n```\n'])


def test_flag_stateful_button_changes_bootstrap5():
    line = """        <button data-loading-text="foo>\n"""
    flags = flag_stateful_button_changes_bootstrap5(line)
    eq(flags, ['You are using stateful buttons here, which are no longer supported in Bootstrap 5.'])


def test_flag_bootstrap3_references_in_template_extends():
    line = """{% extends "hqwebapp/bootstrap3/base_section.html" %}\n"""
    flags = flag_bootstrap3_references_in_template(line)
    eq(flags, ['This template extends a bootstrap 3 template.'])


def test_flag_bootstrap3_references_in_template_requirejs():
    line = """    {% requirejs_main 'hqwebapp/bootstrap3/foo' %}\n"""
    flags = flag_bootstrap3_references_in_template(line)
    eq(flags, ['This template references a bootstrap 3 requirejs file.'])


def test_flag_changed_javascript_plugins_bootstrap5():
    line = """                        modal.modal('show');\n"""
    flags = flag_changed_javascript_plugins(
        line, get_spec('bootstrap_3_to_5')
    )
    eq(flags, ["The `modal` plugin has been restructured since the removal of jQuery.\n\nThere is now a new way "
               "of triggering modal events and interacting with modals in javascript.\nFor instance, if we "
               "wanted to hide a modal with id `#bugReport` before, we would now do the\nfollowing..."
               "\n\nAn EXAMPLE for how to apply this change is provided below.\nPlease see docs for "
               "further details.\n\npreviously\n```\n$('#bugReport').modal('hide');\n```\n\nnow\n```\n"
               "const bugReportModal = new bootstrap.Modal($('#bugReport'));\nbugReportModal.hide();\n```\n\n"
               "Hint: make sure to list `hqwebapp/js/bootstrap5_loader` as a js dependency in the file where\n"
               "bootstrap is referenced.\n\nOld docs: https://getbootstrap.com/docs/3.4/javascript/#modals\n"
               "New docs: https://getbootstrap.com/docs/5.3/components/modal/#via-javascript\n"])


def test_flag_extended_changed_javascript_plugins_bootstrap5():
    line = """    var oldHide = $.fn.popover.Constructor.prototype.hide;\n"""
    flags = flag_changed_javascript_plugins(
        line, get_spec('bootstrap_3_to_5')
    )
    eq(flags, ['The `popover` plugin has been restructured since the removal of jQuery.\n'
               '\nThere is now a new way of triggering popover events and interacting '
               'with popovers in javascript.\n\nPlease feel free to update this help text'
               ' as you find common replacements/restructuring\nfor our usage of this '
               'plugin. Thanks!\n\nOld docs: https://getbootstrap.com/docs/3.4/'
               'javascript/#popovers\nNew docs: https://getbootstrap.com/docs/5.3/'
               'components/popovers/\n'])


def test_flag_path_references_to_split_javascript_files_bootstrap5():
    line = """    'hqwebapp/js/bootstrap3/crud_paginated_list',\n"""
    flags = flag_path_references_to_split_javascript_files(
        line, "bootstrap3"
    )
    eq(flags, ['Found reference to a split file (bootstrap3)'])


def test_file_contains_reference_to_path():
    filedata = """
    {# Our Libraries #}
    {% if not requirejs_main %}
      {% compress js %}
        <script src="{% static 'foobarapp/js/bugz.js' %}"></script>
        <script src="{% static 'foobarapp/js/privileges.js' %}"></script>
        <script src="{% static 'foobarapp/js/alert_user.js' %}"></script>
      {% endcompress %}
    {% endif %}"""
    contains_ref = file_contains_reference_to_path(filedata, "foobarapp/js/bugz.js")
    eq(contains_ref, True)


def test_file_does_not_contain_reference_to_path():
    filedata = """
    {# Our Libraries #}
    {% if not requirejs_main %}
      {% compress js %}
        <script src="{% static 'foobarapp/js/bugz_two.js' %}"></script>
        <script src="{% static 'foobarapp/js/privileges.js' %}"></script>
        <script src="{% static 'foobarapp/js/alert_user.js' %}"></script>
      {% endcompress %}
    {% endif %}"""
    contains_ref = file_contains_reference_to_path(filedata, "foobarapp/js/bugz.js")
    eq(contains_ref, False)


def test_javascript_file_contains_reference_to_path():
    filedata = """hqDefine('foobarapp/js/bugz_two', [
        'foobarapp/js/bugz'
        'foobarapp/js/layout'
    ], function() {
        // nothing to do, this is just to define the dependencies for foobarapp/base.html
    });"""
    contains_ref = file_contains_reference_to_path(filedata, "foobarapp/js/bugz")
    eq(contains_ref, True)


def test_javascript_file_does_not_contain_reference_to_path():
    filedata = """hqDefine('foobarapp/js/bugz_two', [
        'foobarapp/js/layout'
    ], function() {
        // nothing to do, this is just to define the dependencies for foobarapp/base.html
    });"""
    contains_ref = file_contains_reference_to_path(filedata, "foobarapp/js/bugz")
    eq(contains_ref, False)


def test_replace_path_references():
    filedata = """
    {# Our Libraries #}
    {% if not requirejs_main %}
      {% compress js %}
        <script src="{% static 'foobarapp/js/bugz.js' %}"></script>
        <script src="{% static 'foobarapp/js/privileges.js' %}"></script>
        <script src="{% static 'foobarapp/js/alert_user.js' %}"></script>
      {% endcompress %}
    {% endif %}
    <script src="{% static "foobarapp/js/bugz.js" %}"></script>
    """
    result = replace_path_references(filedata, "foobarapp/js/bugz.js", "foobarapp/js/bootstrap3/bugz.js")
    expected_result = """
    {# Our Libraries #}
    {% if not requirejs_main %}
      {% compress js %}
        <script src="{% static 'foobarapp/js/bootstrap3/bugz.js' %}"></script>
        <script src="{% static 'foobarapp/js/privileges.js' %}"></script>
        <script src="{% static 'foobarapp/js/alert_user.js' %}"></script>
      {% endcompress %}
    {% endif %}
    <script src="{% static "foobarapp/js/bootstrap3/bugz.js" %}"></script>
    """
    eq(result, expected_result)


def test_replace_path_references_javascript():
    filedata = """hqDefine('foobarapp/js/bugz_two', [
    'foobarapp/js/bugz',
    'foobarapp/js/layout'
], function() {
    // nothing to do, this is just to define the dependencies for foobarapp/base.html
});"""
    result = replace_path_references(filedata, "foobarapp/js/bugz", "foobarapp/js/bootstrap3/bugz")
    expected_result = """hqDefine('foobarapp/js/bugz_two', [
    'foobarapp/js/bootstrap3/bugz',
    'foobarapp/js/layout'
], function() {
    // nothing to do, this is just to define the dependencies for foobarapp/base.html
});"""
    eq(result, expected_result)
