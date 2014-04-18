def homescreen_title():
    return 'homescreen.title'


def app_display_name():
    return "app.display.name"


def detail_title_locale(module, detail_type):
    return u"m{module.id}.{detail_type}.title".format(module=module,
                                                      detail_type=detail_type)


def detail_column_header_locale(module, detail_type, column):
    return u"m{module.id}.{detail_type}.{d.model}_{d.field}_{d_id}.header".format(
        detail_type=detail_type,
        module=module,
        d=column,
        d_id=column.id + 1
    )


def detail_column_enum_variable(module, detail_type, column, key):
    return u"m{module.id}.{detail_type}.{d.model}_{d.field}_{d_id}.enum.k{key}".format(
        module=module,
        detail_type=detail_type,
        d=column,
        d_id=column.id + 1,
        key=key,
    )


def module_locale(module):
    return u"modules.m{module.id}".format(module=module)


def form_locale(form):
    return u"forms.m{module.id}f{form.id}".format(module=form.get_module(),
                                                  form=form)


def case_list_locale(module):
    return u"case_lists.m{module.id}".format(module=module)


def referral_list_locale(module):
    """1.0 holdover"""
    return u"referral_lists.m{module.id}".format(module=module)


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
    return u'root' if put_in_root else u"m{module.id}".format(module=module)


def form_command(form):
    return u"m{module.id}-f{form.id}".format(module=form.get_module(), form=form)


def case_list_command(module):
    return u"m{module.id}-case-list".format(module=module)


def referral_list_command(module):
    """1.0 holdover"""
    return u"m{module.id}-referral-list".format(module=module)


def indicator_instance(indicator_set_name):
    return u"indicators_%s" % indicator_set_name
