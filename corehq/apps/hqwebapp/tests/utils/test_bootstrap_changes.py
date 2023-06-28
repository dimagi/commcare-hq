from testil import eq
from corehq.apps.hqwebapp.utils.bootstrap.changes import (
    get_spec,
    make_direct_css_renames,
    make_numbered_css_renames,
    make_data_attribute_renames,
    flag_changed_css_classes,
    flag_stateful_button_changes_bootstrap5,
    flag_changed_javascript_plugins,
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
    eq(flags, ['`dl-horizontal` has been dropped.\nInstead, use `.row` on `<dl>` and use grid '
               'column classes (or mixins) on its `<dt>` and `<dd>` children.\n\nPreviously:\n```\n'
               '<dl class="dl-horizontal">\n    <dt>foo</dt>\n    <dd>foo</dd>\n</dl>\n```\n\nNow:'
               '\n```\n<dl class="row">\n    <dt class="col-3">foo</dt>\n    '
               '<dd class="col-9">foo</dd>\n</dl>\n```\n'])


def test_flag_stateful_button_changes_bootstrap5():
    line = """        <button data-loading-text="foo>\n"""
    flags = flag_stateful_button_changes_bootstrap5(line)
    eq(flags, ['You are using stateful buttons here, which are no longer supported in Bootstrap 5.'])


def test_flag_changed_javascript_plugins_bootstrap5():
    line = """                        modal.modal('show');\n"""
    flags = flag_changed_javascript_plugins(
        line, get_spec('bootstrap_3_to_5')
    )
    eq(flags, ['The `modal` plugin has been restructured since the removal of jQuery.\n\n'
               'There is now a new way of triggering modal events and interacting with '
               'modals in javascript.\n\nPlease feel free to update this help text as '
               'you find common replacements/restructuring\nfor our usage of this plugin. '
               'Thanks!\n\nOld docs: https://getbootstrap.com/docs/3.4/javascript/#modals\n'
               'New docs: https://getbootstrap.com/docs/5.3/components/modal/#via-javascript\n'])
