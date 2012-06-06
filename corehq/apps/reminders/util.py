from corehq.apps.app_manager.models import get_app, ApplicationBase

def get_form_list(domain):
    form_list = []
    for app in ApplicationBase.view("app_manager/applications_brief", startkey=[domain], endkey=[domain, {}]):
        latest_app = get_app(domain, app._id, latest=True)
        lang = latest_app.langs[0]
        for m in latest_app.get_modules():
            for f in m.get_forms():
                form_list.append({"code" :  f.unique_id, "name" : app.name + "/" + m.name[lang] + "/" + f.name[lang]})
    return form_list

