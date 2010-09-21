from django.shortcuts import render_to_response
from .models import Application
from corehq.apps.new_xforms.models import XForm

def forms(req, domain="demo", app='', module='', form='', template='hqui/forms.html'):
    print app, module, form

    applications = Application.view('hqui/applications', startkey=[domain], endkey=[domain, {}]).all()
    app = dict([(a.name, a) for a in applications]).get(app, applications[0])
    module = dict([m['name'], m] for m in app.modules).get(module, app.modules[0])
    form = dict([f['name'], f] for f in module['forms']).get(form, module['forms'][0])

    try:
        xform = XForm.get(form['id'])
    except:
        xform = "No such xform"

    return render_to_response(template, {
        'domain': domain,
        'applications': applications,
        'app': app,
        'module': module,
        'form': form,
        'xform': xform
    })
def edit_module(req, domain, app, module, template='hqui/edit_module.html'):
    pass
def new_app(req, domain):
    pass