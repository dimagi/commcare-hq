from corehq.apps.app_manager.models import get_app, ApplicationBase, Form
from couchdbkit.resource import ResourceNotFound
from django.utils.translation import ugettext as _

def get_form_list(domain):
    form_list = []
    for app in ApplicationBase.view("app_manager/applications_brief", startkey=[domain], endkey=[domain, {}]):
        latest_app = get_app(domain, app._id, latest=True)
        if latest_app.doc_type == "Application":
            lang = latest_app.langs[0]
            for m in latest_app.get_modules():
                for f in m.get_forms():
                    try:
                        module_name = m.name[lang]
                    except Exception:
                        module_name = m.name.items()[0][1]
                    try:
                        form_name = f.name[lang]
                    except Exception:
                        form_name = f.name.items()[0][1]
                    form_list.append({"code" :  f.unique_id, "name" : app.name + "/" + module_name + "/" + form_name})
    return form_list

def get_sample_list(domain):
    #Circular import
    from casexml.apps.case.models import CommCareCaseGroup
    
    sample_list = []
    for sample in CommCareCaseGroup.get_all(domain):
        sample_list.append({"code" : sample._id, "name" : sample.name})
    return sample_list

def get_form_name(form_unique_id):
    try:
        form = Form.get_form(form_unique_id)
    except ResourceNotFound:
        return _("[unknown]")
    app = form.get_app()
    module = form.get_module()
    lang = app.langs[0]
    try:
        module_name = module.name[lang]
    except Exception:
        module_name = module.name.items()[0][1]
    try:
        form_name = form.name[lang]
    except Exception:
        form_name = form.name.items()[0][1]
    return app.name + "/" + module_name + "/" + form_name

def get_recipient_name(recipient, include_desc=True):
    # Circular imports
    from corehq.apps.users.models import CouchUser
    from corehq.apps.groups.models import Group
    from casexml.apps.case.models import CommCareCase
    from casexml.apps.case.models import CommCareCaseGroup
    
    if recipient == None:
        return "(no recipient)"
    elif isinstance(recipient, list):
        if len(recipient) > 0:
            return ",".join([get_recipient_name(r, include_desc) for r in recipient])
        else:
            return "(no recipient)"
    elif isinstance(recipient, CouchUser):
        name = recipient.raw_username
        desc = "User"
    elif isinstance(recipient, CommCareCase):
        name = recipient.name
        desc = "Case"
    elif isinstance(recipient, Group):
        name = recipient.name
        desc = "Group"
    elif isinstance(recipient, CommCareCaseGroup):
        name = recipient.name
        desc = "Survey Sample"
    else:
        name = "(unknown)"
        desc = ""
    
    if include_desc:
        return "%s '%s'" % (desc, name)
    else:
        return name


