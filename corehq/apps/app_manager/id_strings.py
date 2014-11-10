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


@pattern('m%d.%s.%s_%s_%s.enum.k%s')
def detail_column_enum_variable(module, detail_type, column, key):
    field = column.field.replace('#', '')
    return u"m{module.id}.{detail_type}.{d.model}_{field}_{d_id}.enum.k{key}".format(
        module=module,
        detail_type=detail_type,
        d=column,
        field=field,
        d_id=column.id + 1,
        key=key,
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


@pattern('referral_lists.m%d')
def referral_list_locale(module):
    """1.0 holdover"""
    return u"referral_lists.m{module.id}".format(module=module)


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


def menu(module):
    put_in_root = getattr(module, 'put_in_root', False)
    return ROOT if put_in_root else u"m{module.id}".format(module=module)


def form_command(form):
    return u"m{module.id}-f{form.id}".format(module=form.get_module(), form=form)


def case_list_command(module):
    return u"m{module.id}-case-list".format(module=module)


def referral_list_command(module):
    """1.0 holdover"""
    return u"m{module.id}-referral-list".format(module=module)


def indicator_instance(indicator_set_name):
    return u"indicators:%s" % indicator_set_name


def schedule_fixture(form):
    return u'schedule:m{module.id}:f{form.id}'.format(module=form.get_module(), form=form)
