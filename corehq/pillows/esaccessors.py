from corehq.apps.es import FormES


def get_last_form_for_apps(apps, user_id):
    forms = []
    for app_id in apps:
        query = FormES().app(app_id).user_id(user_id).sort('received_on', desc=True).size(1)
        hits = query.run().hits
        if hits:
            forms.append(hits[0])
    return forms