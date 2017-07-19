import re

ROOT = u'root'


def _format_to_regex(pattern):
    """
    convert a format string with %s and %d to a regex

    %s => .*
    %d => [0-9]+
    %% => %

    everything else gets `re.escape`d

    >>> import re
    >>> format = '%shello %%sam %s, you are %d years old.'
    >>> regex = _format_to_regex(format)
    >>> print regex
    .*hello\ %sam\ .*\,\ you\ are\ [0-9]+\ years\ old\.
    >>> bool(re.match(regex, format % ("Oh ", "i am", 6)))
    True
    >>> bool(re.match(regex, format))
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


REGEXES = []


def pattern(*patterns):
    for pattern in patterns:
        REGEXES.append(_format_to_regex(pattern))
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


@pattern('m%d.%s.title')
def detail_title_locale(detail_type):
    if detail_type.startswith('case'):
        return "cchq.case"
    elif detail_type.startswith('referral'):
        return "cchq.referral"


@pattern('m%d.%s.tab.%d.title')
def detail_tab_title_locale(module, detail_type, tab):
    return u"m{module.id}.{detail_type}.tab.{tab_index}.title".format(
        module=module,
        detail_type=detail_type,
        tab_index=tab.id + 1
    )


@pattern('m%d.%s.%s_%s_%d.header')
def detail_column_header_locale(module, detail_type, column):
    field = column.field.replace('#', '')
    return u"m{module.id}.{detail_type}.{d.model}_{field}_{d_id}.header".format(
        detail_type=detail_type,
        module=module,
        d=column,
        field=field,
        d_id=column.id + 1
    )


@pattern('m%d.%s.%s_%s_%s.enum.%s')
def detail_column_enum_variable(module, detail_type, column, key_as_var):
    field = column.field.replace('#', '')
    return u"m{module.id}.{detail_type}.{d.model}_{field}_{d_id}.enum.{key_as_var}".format(
        module=module,
        detail_type=detail_type,
        d=column,
        field=field,
        d_id=column.id + 1,
        key_as_var=key_as_var,
    )


@pattern('m%d.%s.%s_%s_%s.graph.key.%s')
def graph_configuration(module, detail_type, column, key):
    field = column.field.replace('#', '')
    return u"m{module.id}.{detail_type}.{d.model}_{field}_{d_id}.graph.key.{key}".format(
        module=module,
        detail_type=detail_type,
        d=column,
        field=field,
        d_id=column.id + 1,
        key=key
    )


@pattern('m%d.%s.graph.key.%s')
def mobile_ucr_configuration(module, uuid, key):
    return u"m{module.id}.{uuid}.graph.key.{key}".format(
        module=module,
        uuid=uuid,
        key=key
    )


@pattern('m%d.%s.%s_%s_%s.graph.series_%d.key.%s')
def graph_series_configuration(module, detail_type, column, series_index, key):
    field = column.field.replace('#', '')
    return u"m{module.id}.{detail_type}.{d.model}_{field}_{d_id}.graph.series_{series_index}.key.{key}".format(
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
    return u"m{module.id}.{uuid}.graph.series_{series_index}.key.{key}".format(
        module=module,
        uuid=uuid,
        series_index=series_index,
        key=key
    )


@pattern('m%d.%s.%s_%s_%s.graph.a.%d')
def graph_annotation(module, detail_type, column, annotation_index):
    field = column.field.replace('#', '')
    return u"m{module.id}.{detail_type}.{d.model}_{field}_{d_id}.graph.a.{a_id}".format(
        module=module,
        detail_type=detail_type,
        d=column,
        field=field,
        d_id=column.id + 1,
        a_id=annotation_index
    )


@pattern('m%d.%s.graph.a.%d')
def mobile_ucr_annotation(module, uuid, annotation_index):
    return u"m{module.id}.{uuid}.graph.a.{a_id}".format(
        module=module,
        uuid=uuid,
        a_id=annotation_index
    )


@pattern('modules.m%d')
def module_locale(module):
    return u"modules.m{module.id}".format(module=module)


@pattern('forms.m%df%d')
def form_locale(form):
    return u"forms.m{module.id}f{form.id}".format(module=form.get_module(),
                                                  form=form)


@pattern('case_lists.m%d')
def case_list_locale(module):
    return u"case_lists.m{module.id}".format(module=module)


@pattern('case_list_form.m%d')
def case_list_form_locale(module):
    return u"case_list_form.m{module.id}".format(module=module)


@pattern('case_lists.m%d.callout.header')
def callout_header_locale(module):
    return u"case_lists.m{module.id}.callout.header".format(module=module)


@pattern('case_search.m%d')
def case_search_locale(module):
    return u"case_search.m{module.id}".format(module=module)


@pattern('search_command.m%d')
def search_command(module):
    return u"search_command.m{module.id}".format(module=module)


@pattern('search_property.m%d.%s')
def search_property_locale(module, search_prop):
    return u"search_property.m{module.id}.{search_prop}".format(module=module, search_prop=search_prop)


@pattern('referral_lists.m%d')
def referral_list_locale(module):
    """1.0 holdover"""
    return u"referral_lists.m{module.id}".format(module=module)


@pattern('reports.%s')
def report_command(report_id):
    return u'reports.{report_id}'.format(report_id=report_id)


@pattern('cchq.report_menu')
def report_menu():
    return u'cchq.report_menu'


@pattern('cchq.report_name_header')
def report_name_header():
    return u'cchq.report_name_header'


@pattern('cchq.report_description_header')
def report_description_header():
    return u'cchq.report_description_header'


@pattern('cchq.report_data_table')
def report_data_table():
    return u'cchq.report_data_table'


@pattern('cchq.reports.%s.headers.%s')
def report_column_header(report_id, column):
    return u'cchq.reports.{report_id}.headers.{column}'.format(report_id=report_id, column=column)


@pattern('cchq.reports.%s.name')
def report_name(report_id):
    return u'cchq.reports.{report_id}.name'.format(report_id=report_id)


@pattern('cchq.reports.%s.description')
def report_description(report_id):
    return u'cchq.reports.{report_id}.description'.format(report_id=report_id)


@pattern('cchq.report_last_sync')
def report_last_sync():
    return u'cchq.report_last_sync'


CUSTOM_APP_STRINGS_RE = _regex_union(REGEXES)


def is_custom_app_string(key):
    return bool(re.match(CUSTOM_APP_STRINGS_RE, key))


# non "app-string" id strings:

def xform_resource(form):
    return form.unique_id


def locale_resource(lang):
    return u'app_{lang}_strings'.format(lang=lang)


def media_resource(multimedia_id, name):
    return u'media-{id}-{name}'.format(id=multimedia_id, name=name)


@pattern('modules.m%d.icon')
def module_icon_locale(module):
    return u"modules.m{module.id}.icon".format(module=module)


@pattern('modules.m%d.audio')
def module_audio_locale(module):
    return u"modules.m{module.id}.audio".format(module=module)


@pattern('forms.m%df%d.icon')
def form_icon_locale(form):
    return u"forms.m{module.id}f{form.id}.icon".format(
        module=form.get_module(),
        form=form
    )


@pattern('forms.m%df%d.audio')
def form_audio_locale(form):
    return u"forms.m{module.id}f{form.id}.audio".format(
        module=form.get_module(),
        form=form
    )


@pattern('case_list_form.m%d.icon')
def case_list_form_icon_locale(module):
    return u"case_list_form.m{module.id}.icon".format(module=module)


@pattern('case_list_form.m%d.audio')
def case_list_form_audio_locale(module):
    return u"case_list_form.m{module.id}.audio".format(module=module)


@pattern('case_lists.m%d.icon')
def case_list_icon_locale(module):
    return u"case_lists.m{module.id}.icon".format(module=module)


@pattern('case_lists.m%d.audio')
def case_list_audio_locale(module):
    return u"case_lists.m{module.id}.audio".format(module=module)


def detail(module, detail_type):
    return u"m{module.id}_{detail_type}".format(module=module, detail_type=detail_type)


def persistent_case_context_detail(module):
    return detail(module, 'persistent_case_context')


def fixture_detail(module):
    return detail(module, 'fixture_select')


def fixture_session_var(module):
    return u'fixture_value_m{module.id}'.format(module=module)


def menu_id(module, suffix=""):
    put_in_root = getattr(module, 'put_in_root', False)
    if put_in_root:
        # handle circular calls, if bad module workflow setup
        return menu_id(module.root_module) if getattr(module, 'root_module', False) else ROOT
    else:
        if suffix:
            suffix = ".{}".format(suffix)
        return u"m{module.id}{suffix}".format(module=module, suffix=suffix)


def form_command(form, module=None):
    if not module:
        module = form.get_module()
    return u"m{module.id}-f{form.id}".format(module=module, form=form)


def case_list_command(module):
    return u"m{module.id}-case-list".format(module=module)


def referral_list_command(module):
    """1.0 holdover"""
    return u"m{module.id}-referral-list".format(module=module)


def indicator_instance(indicator_set_name):
    return u"indicators:%s" % indicator_set_name


def schedule_fixture(module, phase, form):
    form_id = phase.get_phase_form_index(form)
    return u'schedule:m{module.id}:p{phase.id}:f{form_id}'.format(module=module, phase=phase, form_id=form_id)
