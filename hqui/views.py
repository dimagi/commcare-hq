from corehq.util.webutils import render_to_response
from .models import Application
from corehq.apps.new_xforms.models import XForm
from corehq.apps.new_xforms.views import _register_xform
from hqui.forms import NewXFormForm, NewAppForm, NewModuleForm
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from corehq.util.xforms import readable_form

def _tidy(name):
    return name.replace('_', ' ').replace('-', ' ').title()
def _forms_context(req, domain="demo", app='', module='', form=''):

    applications = Application.view('hqui/applications', startkey=[domain], endkey=[domain, {}]).all()
    if app:
        app = Application.view('hqui/applications', key=[domain, app]).one()
        module = dict([m['name'], m] for m in app.modules).get(module, {'forms':''})
        form = dict([f['name'], f] for f in module['forms']).get(form, '')

    try:
        xform = XForm.get(form['id'])
    except:
        xform = ""
    if xform:
        xform_contents = xform.fetch_attachment('xform.xml').encode('utf-8')
        #xform_contents, err, has_err = readable_form(xform_contents)

    else:
        xform_contents = ''
    return {
        'domain': domain,
        'applications': applications,
        'app': app,
        'module': module,
        'form': form,
        'xform': xform,
        'xform_contents': xform_contents,
        'new_app_form': NewAppForm(),
        'new_module_form': NewModuleForm(),
    }

def forms(req, domain="demo", app='', module='', form='', template='hqui/forms.html'):
    context = _forms_context(req, domain, app, module, form)
    print "%r" % (context['xform_contents'])
    return render_to_response(req, template, context)
def new_module(req, domain, app):
    if req.method == "POST":
        form = NewModuleForm(req.POST)
        if form.is_valid():
            cd = form.cleaned_data
            app = Application.view('hqui/applications', key=[domain, app]).one()
            if cd['name'] not in [m['name'] for m in app.modules]:
                app.modules.append({'name':cd['name'], 'forms': []})
                app.save()
    return HttpResponseRedirect(reverse('hqui.views.forms', args=[domain, app.name, cd['name']]))
def new_app(req, domain):
    if req.method == "POST":
        form = NewAppForm(req.POST)
        if form.is_valid():
            cd = form.cleaned_data
            if Application.view('hqui/applications', key=[domain, cd['name']]).count() == 0:
                app = Application(domain=domain, name=cd['name'], modules=[], trans={'en': _tidy(cd['name'])})
                app.save()
    return HttpResponseRedirect(reverse('hqui.views.forms', args=[domain, app.name]))
def new_form(req, domain, app, module, template="hqui/new_form.html"):
    if req.method == "POST":
        form = NewXFormForm(req.POST, req.FILES)

        if form.is_valid():
            cd = form.cleaned_data
            doc = _register_xform(
                attachment=cd['file'],
                display_name=cd['name'],
                domain=domain
            )
            context = _forms_context(req, domain, app, module, cd['name'])
            # module and form are not copies, so modifying them modifies app
            form = {
                'name': cd['name'],
                'id': doc['_id']
            }
            if context['form']:
                context['form'].update(form)
            else:
                context['module']['forms'].append(form)
            context['app'].save()
            return HttpResponseRedirect(reverse('hqui.views.forms', args=[domain, app, module, form['name']]))

    context = _forms_context(req, domain, app, module)
    form_name = req.GET.get('form_name', '')
    context.update(
        new_xform_form  = NewXFormForm(initial={'name':form_name}),
    )
    return render_to_response(req, template, context)
def delete_form(req, domain, app, module, form):
    app = Application.view('hqui/applications', key=[domain, app]).one()
    module = dict([(x['name'],x) for x in app.modules])[module]
    for i,f in enumerate(module['forms']):
        if f['name'] == form:
            del module['forms'][i]
            break
    app.save()
    return HttpResponseRedirect(reverse('hqui.views.forms', args=[domain, app.name]))