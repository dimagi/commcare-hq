from corehq.apps.app_manager.models import get_app, ApplicationBase, Form

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
    from corehq.apps.reminders.models import SurveySample
    
    sample_list = []
    for sample in SurveySample.view("reminders/sample_by_domain", startkey=[domain], endkey=[domain, {}], include_docs=True):
        sample_list.append({"code" : sample._id, "name" : sample.name})
    return sample_list

def get_form_name(form_unique_id):
    form = Form.get_form(form_unique_id)
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


