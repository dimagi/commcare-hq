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


@pattern('m%d.%s.title')
def detail_title_locale(module, detail_type):
    return u"m{module.id}.{detail_type}.title".format(module=module,
                                                      detail_type=detail_type)


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


@pattern('cchq.reports.%s.headers.%s')
def report_column_header(report_id, column):
    return u'cchq.reports.{report_id}.headers.{column}'.format(report_id=report_id, column=column)


@pattern('cchq.reports.%s.name')
def report_name(report_id):
    return u'cchq.reports.{report_id}.name'.format(report_id=report_id)


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


def detail(module, detail_type):
    return u"m{module.id}_{detail_type}".format(module=module, detail_type=detail_type)


def menu_id(module):
    put_in_root = getattr(module, 'put_in_root', False)
    if put_in_root:
        # handle circular calls, if bad module workflow setup
        return menu_id(module.root_module) if getattr(module, 'root_module', False) else ROOT
    else:
        return u"m{module.id}".format(module=module)


def menu_root(module):
    put_in_root = getattr(module, 'put_in_root', False)
    if not put_in_root and getattr(module, 'root_module', False):
        return menu_id(module.root_module)
    else:
        return None


def form_command(form):
    return u"m{module.id}-f{form.id}".format(module=form.get_module(), form=form)


def case_list_command(module):
    return u"m{module.id}-case-list".format(module=module)


def referral_list_command(module):
    """1.0 holdover"""
    return u"m{module.id}-referral-list".format(module=module)


def indicator_instance(indicator_set_name):
    return u"indicators:%s" % indicator_set_name


def schedule_fixture(module, phase, form):
    return u'schedule:m{module.id}:p{phase.id}:f{form.id}'.format(module=module, phase=phase, form=form)
