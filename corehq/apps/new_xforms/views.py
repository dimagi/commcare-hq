from couchforms.views import post as couchforms_post
from django.http import HttpResponse
from corehq.util.webutils import render_to_response
from BeautifulSoup import BeautifulStoneSoup
from datetime import datetime
#from collections import defaultdict

from .models import Application, Module, Form, XForm
from .forms import NewXFormForm, NewAppForm, NewModuleForm
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from corehq.util.xforms import readable_form

def _tidy(name):
    return name.replace('_', ' ').title()
def _compify(name):
    return name.replace(' ', '_').lower()
def _forms_context(req, domain="demo", app_id='', module_id='', form_id='', select_first=True):
    #print "%s > %s > %s > %s " % (domain, app_id, module_id, form_id)
    applications = Application.view('new_xforms/applications', startkey=[domain], endkey=[domain, {}]).all()
    app = module = form = None
    if app_id:
        app = Application.get(app_id)
    elif applications and select_first:
        app = applications[0]
    if module_id:
        module = app.get_module(module_id)
    elif app and app.modules and select_first:
        module = app.get_module(0)
    if form_id:
        form = module.get_form(form_id)
    elif module and module['forms'] and select_first:
        form = module.get_form(0)
    xform = ""
    xform_contents = ""
    try:
        xform = XForm.get(form['xform_id'])
    except:
        pass
    if xform:
        #xform_contents = xform.fetch_attachment('xform.xml').encode('utf-8')
        #xform_contents, err, has_err = readable_form(xform_contents)
        xform_contents = ""

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

def forms(req, domain="demo", app_id='', module_id='', form_id='', template='new_xforms/forms.html'):
    edit = (req.GET.get('edit', '') == 'true')
    error = req.GET.get('error', '')
    context = _forms_context(req, domain, app_id, module_id, form_id)
    app = context['app']
    force_edit = False
    if (not context['applications']) or (app and not app.modules):
        edit = True
        force_edit = True
    context.update({
        'edit': edit,
        'force_edit': force_edit,
        'error':error,
    })
    return render_to_response(req, template, context)


def new_app(req, domain):
    if req.method == "POST":
        form = NewAppForm(req.POST)
        if form.is_valid():
            cd = form.cleaned_data
            trans = cd['name']
            all_apps = Application.view('new_xforms/applications', key=[domain]).all()
            if trans in [a.trans['en'] for a in all_apps]:
                error="app_exists"
            else:
                app = Application(domain=domain, modules=[], trans={'en': trans})
                app.save()
                return HttpResponseRedirect(
                    reverse('corehq.apps.new_xforms.views.forms', args=[domain, app['_id']])
                    + "?edit=true"
                )

        else:
            error="app_form_invalid"
    else:
        error="wtf"
    return HttpResponseRedirect(
        reverse('corehq.apps.new_xforms.views.forms', args=[domain])
        + "?edit=true" + ";error=%s" % error
    )

def new_module(req, domain, app_id):
    if req.method == "POST":
        form = NewModuleForm(req.POST)
        if form.is_valid():
            cd = form.cleaned_data
            trans = cd['name']
            app = Application.get(app_id)
            if trans in [m['trans']['en'] for m in app.modules]:
                error = "module_exists"
            else:
                module_id = len(app.modules)
                app.modules.append({'trans': {'en': trans}, 'forms': []})
                app.save()
                return HttpResponseRedirect(
                    reverse('corehq.apps.new_xforms.views.forms', args=[domain, app_id, module_id])
                    + "?edit=true"
                )
        else:
            error = "module_form_invalid"
    else:
        error = "wtf"

    return HttpResponseRedirect(
        reverse('corehq.apps.new_xforms.views.forms', args=[domain, app_id])
        + "?edit=true" + ";error=%s" % error
    )
def new_form(req, domain, app_id, module_id, template="new_xforms/new_form.html"):
    if req.method == "POST":
        form = NewXFormForm(req.POST, req.FILES)

        if form.is_valid():
            cd = form.cleaned_data
            trans = cd['name']
            doc = _register_xform(
                attachment=cd['file'],
                display_name=trans,
                domain=domain
            )
            context = _forms_context(req, domain, app_id, module_id, select_first=False)
            # module and form are not copies, so modifying them modifies app
            form = {
                'trans': {'en': cd['name']},
                'xform_id': doc['_id']
            }
            if context['form']:
                context['form'].update(form)
                form_id = context['form'].id
            else:
                form_id = len(context['module']['forms'])
                context['module']['forms'].append(form)
            context['app'].save()
            return HttpResponseRedirect(
                reverse('corehq.apps.new_xforms.views.forms', args=[domain, app_id, module_id, form_id])
                + "?edit=true"
            )

    context = _forms_context(req, domain, app_id, module_id)
    form_name = req.GET.get('form_name', '')
    context.update({
        'new_xform_form': NewXFormForm(initial={'name':form_name}),
        'edit': True,
        'view_name': "new_form"
    })
    return render_to_response(req, template, context)

def delete_app(req, domain, app_id):
    Application.get(app_id).delete()
    return HttpResponseRedirect(
        reverse('corehq.apps.new_xforms.views.forms', args=[domain])
        + "?edit=true"
    )

def delete_module(req, domain, app_id, module_id):
    app = Application.get(app_id)
    del app.modules[int(module_id)]
    app.save()
    return HttpResponseRedirect(
        reverse('corehq.apps.new_xforms.views.forms', args=[domain, app_id])
        + "?edit=true"
    )

def delete_form(req, domain, app_id, module_id, form_id):
    app = Application.get(app_id)
    module = Module(app, module_id)
    del module['forms'][int(form_id)]
    app.save()
    return HttpResponseRedirect(
        reverse('corehq.apps.new_xforms.views.forms', args=[domain, app_id])
        + "?edit=true"
    )


def _register_xform(display_name, attachment, domain):
    if not isinstance(attachment, basestring):
        attachment = attachment.read()
    doc = XForm()
    doc.display_name = display_name
    soup = BeautifulStoneSoup(attachment)
    doc.xmlns = soup.find('instance').findChild()['xmlns']

    doc.submit_time = datetime.utcnow()
    doc.domain = domain

    doc.save()
    doc.put_attachment(attachment, 'xform.xml', content_type='text/xml')
    return doc
    
# def post(request):
#     def callback(doc):
#         doc['submit_ip'] = request.META['REMOTE_ADDR']
#         #doc['domain'] = request.user.selected_domain()
#         doc.save()
#         return HttpResponse("%s\n" % doc['_id'])
#     return couchforms_post(request, callback)
# 
# def dashboard(request, template='new_xforms/register_xform.html'):
#     domain = request.user.selected_domain.name
#     if(len(request.FILES) == 1):
#         for name in request.FILES:
#             doc = _register_xform(
#                 attachment=request.FILES[name],
#                 display_name=request.POST.get('form_display_name', ''),
#                 domain=domain
#             )
# 
#     xforms = XForm.view('new_xforms/by_domain', startkey=[domain], endkey=[domain, {}]).all()
#     by_xmlns = defaultdict(list)
#     for xform in xforms:
#         by_xmlns[xform.xmlns].append(xform)
#     form_groups = []
#     for _, forms in by_xmlns.items():
#         fg = {}
#         for attr in ('xmlns', 'display_name', 'domain'):
#             fg[attr] = forms[-1][attr]
#         fg['forms'] = forms
#         fg['first_date_registered'] = forms[0].submit_time
#         form_groups.append(fg)
# 
#     return render_to_response(request, template, {
#         'upload_form': RegisterXForm(),
#         'form_groups': form_groups
#     })