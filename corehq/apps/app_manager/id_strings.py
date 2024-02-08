import re

ROOT = 'root'


def _format_to_regex(pattern):
    r"""
    convert a format string with %s and %d to a regex

    %s => .*
    %d => [0-9]+
    %% => %

    everything else gets `re.escape`d

    >>> import re
    >>> format_ = '%shello %%sam %s you are %d years old.'
    >>> regex = _format_to_regex(format_)
    >>> print(regex)
    .*hello\ %sam\ .*\ you\ are\ [0-9]+\ years\ old\.
    >>> bool(re.match(regex, format_ % ("Oh ", "i am", 6)))
    True
    >>> bool(re.match(regex, format_))
    False

    """
    formatting_re = r'%[%sd]'
    parts = [re.escape(part) for part in re.split(formatting_re, pattern)]
    replacements = [{'%s': '.*', '%d': '[0-9]+', '%%': '%'}[r]
                    for r in re.findall(formatting_re, pattern)]
    result = parts.pop(0)
    for p, r in zip(parts, replacements):
        result += r + p

    return result


def _regex_union(regexes):
    return '|'.join('({})'.format(regex) for regex in regexes)


def _clean_field_for_mobile(field):
    """Used for translations that are intended to be sent down to mobile in app_strings.txt
    Both # and = are un-escapable in this file, so lets remove them and cross our fingers
    that no one ever wants some_property and some_#property as fields in the same case list
    """
    return field.replace('#', '').replace('=', '')


REGEXES = []
REGEX_DEFAULT_VALUES = {}


# Do not use this outside of this module, since it modifies module-level variables
def pattern(pattern, default=None):
    REGEXES.append(_format_to_regex(pattern))
    if default:
        REGEX_DEFAULT_VALUES[pattern] = default

    return lambda fn: fn


@pattern('homescreen.title')
def homescreen_title():
    return 'homescreen.title'


@pattern('app.display.name')
def app_display_name():
    return "app.display.name"


@pattern('lang.current')
def current_language():
    return "lang.current"


@pattern('cchq.case', default="Case")
def _case_detail_title_locale():
    return 'cchq.case'


@pattern('cchq.referral', default="Referral")
def _referral_detail_title_locale():
    return 'cchq.referral'


@pattern('m%d.%s.title')
def detail_title_locale(detail_type):
    if detail_type.startswith('case') or detail_type.startswith('search'):
        return _case_detail_title_locale()
    elif detail_type.startswith('referral'):
        return _referral_detail_title_locale()


@pattern('m%d.%s.tab.%d.title')
def detail_tab_title_locale(module, detail_type, tab):
    return "m{module.id}.{detail_type}.tab.{tab_index}.title".format(
        module=module,
        detail_type=detail_type,
        tab_index=tab.id + 1
    )


@pattern('m%d.%s.%s_%s_%d.header')
def detail_column_header_locale(module, detail_type, column):
    if column.useXpathExpression:
        field = 'calculated_property'
    else:
        field = _clean_field_for_mobile(column.field)
    return "m{module.id}.{detail_type}.{d.model}_{field}_{d_id}.header".format(
        detail_type=detail_type,
        module=module,
        d=column,
        field=field,
        d_id=column.id + 1
    )


@pattern('m%d.%s.%s_%s_%s.enum.%s')
def detail_column_enum_variable(module, detail_type, column, key_as_var):
    field = _clean_field_for_mobile(column.field)
    return "m{module.id}.{detail_type}.{d.model}_{field}_{d_id}.enum.{key_as_var}".format(
        module=module,
        detail_type=detail_type,
        d=column,
        field=field,
        d_id=column.id + 1,
        key_as_var=key_as_var,
    )


@pattern('m%d.%s.%s_%s_%s.alt_text.%s')
def detail_column_alt_text_variable(module, detail_type, column, key_as_var):
    field = _clean_field_for_mobile(column.field)
    return "m{module.id}.{detail_type}.{d.model}_{field}_{d_id}.alt_text.{key_as_var}".format(
        module=module,
        detail_type=detail_type,
        d=column,
        field=field,
        d_id=column.id + 1,
        key_as_var=key_as_var,
    )


@pattern('m%d.%s.%s_%s_%s.graph.key.%s')
def graph_configuration(module, detail_type, column, key):
    field = _clean_field_for_mobile(column.field)
    return "m{module.id}.{detail_type}.{d.model}_{field}_{d_id}.graph.key.{key}".format(
        module=module,
        detail_type=detail_type,
        d=column,
        field=field,
        d_id=column.id + 1,
        key=key
    )


@pattern('m%d.%s.graph.key.%s')
def mobile_ucr_configuration(module, uuid, key):
    return "m{module.id}.{uuid}.graph.key.{key}".format(
        module=module,
        uuid=uuid,
        key=key
    )


@pattern('m%d.%s.%s_%s_%s.graph.series_%d.key.%s')
def graph_series_configuration(module, detail_type, column, series_index, key):
    field = _clean_field_for_mobile(column.field)
    return "m{module.id}.{detail_type}.{d.model}_{field}_{d_id}.graph.series_{series_index}.key.{key}".format(
        module=module,
        detail_type=detail_type,
        d=column,
        field=field,
        d_id=column.id + 1,
        series_index=series_index,
        key=key
    )


@pattern('m%d.%s.graph.series_%d.key.%s')
def mobile_ucr_series_configuration(module, uuid, series_index, key):
    return "m{module.id}.{uuid}.graph.series_{series_index}.key.{key}".format(
        module=module,
        uuid=uuid,
        series_index=series_index,
        key=key
    )


@pattern('m%d.%s.%s_%s_%s.graph.a.%d')
def graph_annotation(module, detail_type, column, annotation_index):
    field = _clean_field_for_mobile(column.field)
    return "m{module.id}.{detail_type}.{d.model}_{field}_{d_id}.graph.a.{a_id}".format(
        module=module,
        detail_type=detail_type,
        d=column,
        field=field,
        d_id=column.id + 1,
        a_id=annotation_index
    )


@pattern('m%d.%s.graph.a.%d')
def mobile_ucr_annotation(module, uuid, annotation_index):
    return "m{module.id}.{uuid}.graph.a.{a_id}".format(
        module=module,
        uuid=uuid,
        a_id=annotation_index
    )


@pattern('modules.m%d')
def module_locale(module):
    return "modules.m{module.id}".format(module=module)


@pattern('forms.m%df%d')
def form_locale(form):
    return "forms.m{module.id}f{form.id}".format(module=form.get_module(), form=form)


@pattern('training.root.title')
def training_module_locale():
    return 'training.root.title'


@pattern('case_lists.m%d')
def case_list_locale(module):
    return "case_lists.m{module.id}".format(module=module)


@pattern('case_list_form.m%d')
def case_list_form_locale(module):
    return "case_list_form.m{module.id}".format(module=module)


@pattern('case_lists.m%d.callout.header')
def callout_header_locale(module):
    return "case_lists.m{module.id}.callout.header".format(module=module)


@pattern('case_search.m%d')
def case_search_locale(module):
    return "case_search.m{module.id}".format(module=module)


@pattern('case_search.m%d.icon')
def case_search_icon_locale(module):
    return "case_search.m{module.id}.icon".format(module=module)


@pattern('case_search.m%d.audio')
def case_search_audio_locale(module):
    return "case_search.m{module.id}.audio".format(module=module)


@pattern('case_search.m%d.again')
def case_search_again_locale(module):
    return "case_search.m{module.id}.again".format(module=module)


@pattern('case_search_again.m%d.again.icon')
def case_search_again_icon_locale(module):
    return "case_search.m{module.id}.again.icon".format(module=module)


@pattern('case_search.m%d.again.audio')
def case_search_again_audio_locale(module):
    return "case_search.m{module.id}.again.audio".format(module=module)


@pattern('search_command.m%d')
def search_command(module):
    return "search_command.m{module.id}".format(module=module)


@pattern('search_property.m%d.%s')
def search_property_locale(module, search_prop):
    return "search_property.m{module.id}.{search_prop}".format(module=module, search_prop=search_prop)


@pattern('search_property.m%d.%s.hint')
def search_property_hint_locale(module, search_prop):
    return "search_property.m{module.id}.{search_prop}.hint".format(module=module, search_prop=search_prop)


@pattern('search_property.m%d.%s.required.text')
def search_property_required_text(module, search_prop):
    return f"search_property.m{module.id}.{search_prop}.required.text"


@pattern('search_property.m%d.%s.validation.%d.text')
def search_property_validation_text(module, search_prop, index):
    return f"search_property.m{module.id}.{search_prop}.validation.{index}.text"


@pattern('custom_assertion.%s.%d')
def custom_assertion_locale(id, module=None, form=None):
    if module and form:
        return 'custom_assertion.m{module.id}.f{form.id}.{id}'.format(module=module, form=form, id=id)
    if module:
        return 'custom_assertion.m{module.id}.{id}'.format(module=module, id=id)
    return 'custom_assertion.root.{id}'.format(id=id)


@pattern('referral_lists.m%d')
def referral_list_locale(module):
    """1.0 holdover"""
    return "referral_lists.m{module.id}".format(module=module)


@pattern('reports.%s')
def report_command(report_id):
    return 'reports.{report_id}'.format(report_id=report_id)


@pattern('cchq.report_menu', default='Reports')
def report_menu():
    return 'cchq.report_menu'


@pattern('cchq.report_name_header', default='Report Name')
def report_name_header():
    return 'cchq.report_name_header'


@pattern('cchq.report_description_header', default='Report Description')
def report_description_header():
    return 'cchq.report_description_header'


@pattern('cchq.report_data_table', default='Data Table')
def report_data_table():
    return 'cchq.report_data_table'


@pattern('cchq.reports.%s.headers.%s')
def report_column_header(report_id, column):
    return 'cchq.reports.{report_id}.headers.{column}'.format(report_id=report_id, column=column)


@pattern('cchq.reports.%s.name')
def report_name(report_id):
    return 'cchq.reports.{report_id}.name'.format(report_id=report_id)


@pattern('cchq.reports.%s.description')
def report_description(report_id):
    return 'cchq.reports.{report_id}.description'.format(report_id=report_id)


@pattern('cchq.report_last_sync', default='Last Sync')
def report_last_sync():
    return 'cchq.report_last_sync'


@pattern('cchq.reports_last_updated_on', default='Reports last updated on')
def reports_last_updated_on():
    return 'cchq.reports_last_updated_on'


@pattern('android.package.name.%s')
def android_package_name(package_id):
    return 'android.package.name.{package_id}'.format(package_id=package_id)


CUSTOM_APP_STRINGS_RE = _regex_union(REGEXES)


def is_custom_app_string(key):
    return bool(re.match(CUSTOM_APP_STRINGS_RE, key))


# non "app-string" id strings:

def xform_resource(form):
    return form.unique_id


def locale_resource(lang):
    return 'app_{lang}_strings'.format(lang=lang)


def media_resource(multimedia_id, name):
    return 'media-{id}-{name}'.format(id=multimedia_id, name=name)


@pattern('modules.m%d.icon')
def module_icon_locale(module):
    return "modules.m{module.id}.icon".format(module=module)


@pattern('modules.m%d.audio')
def module_audio_locale(module):
    return "modules.m{module.id}.audio".format(module=module)


@pattern('modules.m%d.%s')
def module_custom_icon_locale(module, icon_form):
    return "modules.m{module.id}.{icon_form}".format(module=module, icon_form=icon_form)


@pattern('forms.m%df%d.icon')
def form_icon_locale(form):
    return "forms.m{module.id}f{form.id}.icon".format(
        module=form.get_module(),
        form=form
    )


@pattern('forms.m%df%d.audio')
def form_audio_locale(form):
    return "forms.m{module.id}f{form.id}.audio".format(
        module=form.get_module(),
        form=form
    )


@pattern('forms.m%df%d.%s')
def form_custom_icon_locale(form, icon_form):
    return "forms.m{module.id}f{form.id}.{icon_form}".format(
        module=form.get_module(),
        form=form,
        icon_form=icon_form,
    )


@pattern('forms.m%df%d.submit_label')
def form_submit_label_locale(form):
    return "forms.m{module.id}f{form.id}.submit_label".format(
        module=form.get_module(),
        form=form
    )


@pattern('forms.m%df%d.submit_notification_label')
def form_submit_notification_label_locale(form):
    return "forms.m{module.id}f{form.id}.submit_notification_label".format(
        module=form.get_module(),
        form=form
    )


@pattern('case_list_form.m%d.icon')
def case_list_form_icon_locale(module):
    return "case_list_form.m{module.id}.icon".format(module=module)


@pattern('case_list_form.m%d.audio')
def case_list_form_audio_locale(module):
    return "case_list_form.m{module.id}.audio".format(module=module)


@pattern('case_lists.m%d.icon')
def case_list_icon_locale(module):
    return "case_lists.m{module.id}.icon".format(module=module)


@pattern('case_lists.m%d.audio')
def case_list_audio_locale(module):
    return "case_lists.m{module.id}.audio".format(module=module)


@pattern('case_search.m%d.inputs')
def case_search_title_translation(module):
    return "case_search.m{module.id}.inputs".format(module=module)


@pattern('case_search.m%d.description')
def case_search_description_locale(module):
    return "case_search.m{module.id}.description".format(module=module)


def detail(module, detail_type):
    return "m{module.id}_{detail_type}".format(module=module, detail_type=detail_type)


def persistent_case_context_detail(module):
    return detail(module, 'persistent_case_context')


@pattern('m%d_no_items_text')
def no_items_text_detail(module):
    return detail(module, 'no_items_text')


@pattern('m%d_select_text')
def select_text_detail(module):
    return detail(module, 'select_text')


def fixture_detail(module):
    return detail(module, 'fixture_select')


def fixture_session_var(module):
    return 'fixture_value_m{module.id}'.format(module=module)


def menu_id(module, suffix=""):
    put_in_root = getattr(module, 'put_in_root', False)
    if put_in_root:
        # handle circular calls, if bad module workflow setup
        return menu_id(module.root_module) if getattr(module, 'root_module', False) else ROOT
    else:
        if suffix:
            suffix = ".{}".format(suffix)
        return "m{module.id}{suffix}".format(module=module, suffix=suffix)


def form_command(form, module=None):
    if not module:
        module = form.get_module()
    return "m{module.id}-f{form.id}".format(module=module, form=form)


def case_list_command(module):
    return "m{module.id}-case-list".format(module=module)


def referral_list_command(module):
    """1.0 holdover"""
    return "m{module.id}-referral-list".format(module=module)


def indicator_instance(indicator_set_name):
    return "indicators:%s" % indicator_set_name


def schedule_fixture(module, phase, form):
    form_id = phase.get_phase_form_index(form)
    return 'schedule:m{module.id}:p{phase.id}:f{form_id}'.format(module=module, phase=phase, form_id=form_id)
