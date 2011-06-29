from dimagi.utils.couch.database import get_db
from django.core.urlresolvers import reverse


def xmlns_to_name(xmlns, domain, html=False):
    try:
        form = get_db().view('reports/forms_by_xmlns', key=[domain, xmlns], group=True).one()['value']
        langs = ['en'] + form['app']['langs']
    except:
        form = None

    if form:
        module_name = form_name = None
        for lang in langs:
            module_name = module_name if module_name is not None else form['module']['name'].get(lang)
            form_name = form_name if form_name is not None else form['form']['name'].get(lang)
        if module_name is None:
            module_name = "None"
        if form_name is None:
            form_name = "None"
        if html:
            name = "<a href='%s'>%s &gt; %s &gt; %s</a>" % (
                reverse("corehq.apps.app_manager.views.view_app", args=[domain, form['app']['id']])
                + "?m=%s&f=%s" % (form['module']['id'], form['form']['id']),
                form['app']['name'],
                module_name,
                form_name
            )
        else:
            name = "%s > %s > %s" % (form['app']['name'], module_name, form_name)
    else:
        name = xmlns
    return name

