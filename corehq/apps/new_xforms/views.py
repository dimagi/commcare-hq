from couchforms.views import post as couchforms_post
from django.http import HttpResponse
from corehq.util.webutils import render_to_response
from BeautifulSoup import BeautifulStoneSoup
from datetime import datetime
#from collections import defaultdict

from .models import Application, Module, Form, XForm
from corehq.apps.new_xforms.forms import NewXFormForm, NewAppForm, NewModuleForm, ModuleConfigForm
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from corehq.util.xforms import readable_form
from corehq.apps.new_xforms.models import Domain
from StringIO import StringIO
from zipfile import ZipFile, ZIP_DEFLATED
from urllib2 import urlopen

IP = "192.168.7.108:8000"
DETAIL_TYPES = ('case_short', 'case_long', 'ref_short', 'ref_long')

def _tidy(name):
    return name.replace('_', ' ').title()
def _compify(name):
    return name.replace(' ', '_').lower()

def back_to_main(domain, app_id='', module_id='', form_id='', edit=False, **kwargs):
    args = [domain]
    print "module_id: %s" % module_id
    for x in app_id, module_id, form_id:
        if x != '':
            args.append(x)
        else:
            break
    EDIT = "?edit=true" if edit else ""
    view_name = ('forms', 'app_view', 'module_view', 'form_view')[len(args)-1]
    return HttpResponseRedirect(
        reverse('corehq.apps.new_xforms.views.%s' % view_name, args=args)
        + EDIT
    )
def _forms_context(req, domain="demo", app_id='', module_id='', form_id='', select_first=False):
    #print "%s > %s > %s > %s " % (domain, app_id, module_id, form_id)
    edit = (req.GET.get('edit', '') == 'true')
    applications = Application.view('new_xforms/applications', startkey=[domain], endkey=[domain, {}]).all()
    app = module = form = None
    if app_id:
        app = Domain(domain).get_app(app_id)
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
        'edit': edit,
    }

def forms(req, domain="demo", app_id='', module_id='', form_id='', template='new_xforms/forms.html'):
    error = req.GET.get('error', '')
    context = _forms_context(req, domain, app_id, module_id, form_id)
    app = context['app']
    if not app and context['applications']:
        app = context['applications'][0]
    force_edit = False
    if (not context['applications']) or (app and not app.modules):
        edit = True
        force_edit = True
    context.update({
        'force_edit': force_edit,
        'error':error,
        'app': app,
    })
    return render_to_response(req, template, context)

def form_view(req, domain, app_id, module_id, form_id, template="new_xforms/form_view.html"):
    context = _forms_context(req, domain, app_id, module_id, form_id)
    return render_to_response(req, template, context)

def module_view(req, domain, app_id, module_id, template='new_xforms/module_view.html'):
    context = _forms_context(req, domain, app_id, module_id)
    return render_to_response(req, template, context)

def app_view(req, domain, app_id, template="new_xforms/app_view.html"):
    context = _forms_context(req, domain, app_id)
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
                    reverse('corehq.apps.new_xforms.views.app_view', args=[domain, app['_id']])
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
            app = Domain(domain).get_app(app_id)
            if trans in [m['trans']['en'] for m in app.modules]:
                error = "module_exists"
            else:
                module_id = len(app.modules)
                app.modules.append({
                    'trans': {'en': trans},
                    'forms': [],
                    'case_type': '',
                    'details': [{'type': detail_type, 'columns': []} for detail_type in DETAIL_TYPES],
                })
                app.save()
                return HttpResponseRedirect(
                    reverse('corehq.apps.new_xforms.views.module_view', args=[domain, app_id, module_id])
                    + "?edit=true"
                )
        else:
            error = "module_form_invalid"
    else:
        error = "wtf"

    return HttpResponseRedirect(
        reverse('corehq.apps.new_xforms.views.app_view', args=[domain, app_id])
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
                'xform_id': doc['_id'],
                'xmlns': doc['xmlns']
            }
            if context['form']:
                context['form'].update(form)
                form_id = context['form'].id
            else:
                form_id = len(context['module']['forms'])
                context['module']['forms'].append(form)
            context['app'].save()
            return HttpResponseRedirect(
                reverse('corehq.apps.new_xforms.views.form_view', args=[domain, app_id, module_id, form_id])
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
    Domain(domain).get_app(app_id).delete()
    return HttpResponseRedirect(
        reverse('corehq.apps.new_xforms.views.forms', args=[domain])
        + "?edit=true"
    )

def delete_module(req, domain, app_id, module_id):
    app = Domain(domain).get_app(app_id)
    del app.modules[int(module_id)]
    app.save()
    return HttpResponseRedirect(
        reverse('corehq.apps.new_xforms.views.app_view', args=[domain, app_id])
        + "?edit=true"
    )

def delete_form(req, domain, app_id, module_id, form_id):
    app = Domain(domain).get_app(app_id)
    module = Module(app, module_id)
    del module['forms'][int(form_id)]
    app.save()
    return HttpResponseRedirect(
        reverse('corehq.apps.new_xforms.views.app_view', args=[domain, app_id])
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


# module config
#def edit_module_case_type(req, domain, app_id, module_id):
#    if req.method == "POST":
#        case_type = req.POST.get("case_type", None)
#        app = Domain(domain).get_app(app_id)
#        module = app.get_module(module_id)
#        module['case_type'] = case_type
#        app.save()
#    return HttpResponseRedirect(
#        reverse('corehq.apps.new_xforms.views.module_view', args=[domain, app_id, module_id])
#        + "?edit=true"
#    )
def edit_module_attr(req, domain, app_id, module_id, attr):
    if req.method == "POST":
        app = Domain(domain).get_app(app_id)
        module = app.get_module(module_id)
        if   "case_type" == attr:
            case_type = req.POST.get("case_type", None)
            module['case_type'] = case_type
        elif "name" == attr:
            name = req.POST.get("name", None)
            module['trans']['en'] = name
        app.save()
    return HttpResponseRedirect(
        reverse('corehq.apps.new_xforms.views.module_view', args=[domain, app_id, module_id])
        + "?edit=true"
    )
def edit_module_detail(req, domain, app_id, module_id):
    if req.method == "POST":
        column_id = int(req.POST.get('column_id', -1))
        detail_type = req.POST.get('detail_type', '')

        assert(detail_type in DETAIL_TYPES)

        column = dict((key, req.POST[key]) for key in ('header', 'model', 'field', 'format', 'enum'))
        app = Domain(domain).get_app(app_id)
        module = app.get_module(module_id)

        def _enum_to_dict(enum):
            return dict((y.strip() for y in x.strip().split('=')) for x in enum.split(',')) if enum else None

        enum = _enum_to_dict(column['enum'])
        if enum:
            column['enum'] = enum
        for detail in module['details']:
            if detail['type'] == detail_type:
                break
        if detail['type'] != detail_type:
            detail = {'type': detail_type}
            module['details'].append(detail)


        if(column_id == -1):
            detail['columns'].append(column)
        else:
            detail['columns'][column_id] = column
        app.save()

    return HttpResponseRedirect(
        reverse('corehq.apps.new_xforms.views.module_view', args=[domain, app_id, module_id])
        + "?edit=true"
    )
def delete_module_detail(req, domain, app_id, module_id):
    if req.method == "POST":
        column_id = int(req.POST['column_id'])
        detail_type = req.POST['detail_type']
        app = Domain(domain).get_app(app_id)
        module = app.get_module(module_id)
        for detail in module['details']:
            if detail['type'] == detail_type:
                del detail['columns'][column_id]
        app.save()
    return back_to_main(edit=True, **locals())

def edit_form_attr(req, domain, app_id, module_id, form_id, attr):
    if req.method == "POST":
        app = Domain(domain).get_app(app_id)
        form = app.get_module(module_id).get_form(form_id)
        if   "requires" == attr:
            requires = req.POST['requires']
            form['requires'] = requires
        elif "name" == attr:
            name = req.POST['name']
            form['trans']['en'] = name
        elif "xform" == attr:
            xform = req.FILES['xform']
            doc = _register_xform(
                display_name="",
                attachment=xform,
                domain=domain
            )
            form['xform_id'] = doc['_id']
            form['xmlns'] = doc['xmlns']
        elif "show_count" == attr:
            show_count = req.POST['show_count']
            form['show_count'] = True if show_count == "True" else False

        app.save()
    return back_to_main(edit=True, **locals())

def edit_app_lang(req, domain, app_id):
    if req.method == "POST":
        lang = req.POST['lang']
        lang_id = int(req.POST.get('lang_id', -1))
        app = Domain(domain).get_app(app_id)
        if lang_id == -1:
            app.langs.append(lang)
        else:
            app.langs[lang_id] = lang
        app.save()
    return back_to_main(edit=True, **locals())

def delete_app_lang(req, domain, app_id):
    if req.method == "POST":
        lang_id = int(req.POST['lang_id'])
        app = Domain(domain).get_app(app_id)
        del app.langs[lang_id]
        app.save()
    return back_to_main(edit=True, **locals())

def swap(req, domain, app_id, key):
    if req.method == "POST":
        app = Domain(domain).get_app(app_id)
        i, j = (int(x) for x in (req.POST['to'], req.POST['from']))
        assert(i < j)
        if   "forms" == key:
            module_id = int(req.POST['module_id'])
            forms = app.modules[module_id]['forms']
            forms.insert(i, forms.pop(j))
            # I didn't think I'd have to do this, but it makes it work...
            app.modules[module_id]['forms'] = forms
        elif "modules" == key:
            modules = app.modules
            modules.insert(i, modules.pop(j))
            app.modules = modules
        elif "detail" == key:
            module_id = int(req.POST['module_id'])
            detail_type = req.POST['detail_type']
            module = app.get_module(module_id)
            detail = module['details'][DETAIL_TYPES.index(detail_type)]
            columns = detail['columns']
            columns.insert(i, columns.pop(j))
            detail['columns'] = columns
        elif "langs" == key:
            langs = app.langs
            langs.insert(i, langs.pop(j))
            app.langs = langs
        app.save()
    return back_to_main(edit=True, **locals())



def download_profile(req, domain, app_id, template='new_xforms/profile.xml'):
    return render_to_response(req, template, {
        'suite_location': 'http://%s/demo/forms/download/%s/suite.xml' % (IP, app_id)
    })
def download_suite(req, domain, app_id, template='new_xforms/suite.xml'):
    app = Domain(domain).get_app(app_id)
    return render_to_response(req, template, {
        'app': app
    })
def download_app_strings(req, domain, app_id, lang, template='new_xforms/app_strings.txt'):
    app = Domain(domain).get_app(app_id)
    return render_to_response(req, template, {
        'app': app,
        'lang': lang
    })
def download_xform(req, domain, app_id, module_id, form_id):
    xform_id = Domain(domain).get_app(app_id).get_module(module_id).get_form(form_id)['xform_id']
    xform = XForm.get(xform_id)
    xform_xml = xform.fetch_attachment('xform.xml')
    return HttpResponse(xform_xml)

def download(req, domain, app_id):
    response = HttpResponse(mimetype="application/zip")
    response['Content-Disposition'] = "filename=commcare_app.zip"
    app = Domain(domain).get_app(app_id)
    base = "http://%s/demo/forms/download/%s/" % (IP, app_id)
    paths = ["profile.xml", "suite.xml"]
    for lang in app.langs:
        paths.append("%s/app_strings.txt" % lang)
    for module in app.get_modules():
        for form in module.get_forms():
            paths.append("m%s/f%s.xml" % (module.id, form.id))
    print paths
    buffer = StringIO()
    zipper = ZipFile(buffer, 'w', ZIP_DEFLATED)
    for path in paths:
        print path
        zipper.writestr(path, urlopen(base + path).read())
    zipper.close()
    buffer.flush()
    response.write(buffer.getvalue())
    buffer.close()
    return response




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