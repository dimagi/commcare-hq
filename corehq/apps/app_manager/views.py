from django.http import HttpResponse, Http404
from corehq.util.webutils import render_to_response
from BeautifulSoup import BeautifulStoneSoup
from datetime import datetime

from corehq.apps.app_manager.forms import NewXFormForm, NewAppForm, NewModuleForm

from corehq.apps.domain.decorators import login_and_domain_required

from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse, resolve
from corehq.apps.app_manager.models import RemoteApp, Application, Module, XForm, VersionedDoc, get_app, DetailColumn

from corehq.util.webutils import URL_BASE

from corehq.apps.app_manager.models import DETAIL_TYPES


@login_and_domain_required
def back_to_main(req, domain, app_id='', module_id='', form_id='', edit=False, **kwargs):
    params = {}
    if edit:
        params['edit'] = 'true'
    args = [domain]
    print "module_id: %s" % module_id
    for x in app_id, module_id, form_id:
        if x != '':
            args.append(x)
        else:
            break
    def urlize(params):
        if params:
            return '?' + ';'.join(["%s=%s" % (key,val) for key,val in params.items()])
        else:
            return ""
    view_name = ('forms', 'app_view', 'module_view', 'form_view')[len(args)-1]
    return HttpResponseRedirect(
        reverse('corehq.apps.app_manager.views.%s' % view_name, args=args)
        + urlize(params)
    )
def _forms_context(req, domain, app_id='', module_id='', form_id='', select_first=False):
    #print "%s > %s > %s > %s " % (domain, app_id, module_id, form_id)
    edit = (req.GET.get('edit', '') == 'true')
    lang = req.GET.get('lang',
       req.COOKIES.get('lang', '')
    )

    applications = []
    str_to_cls = {"Application":Application, "RemoteApp":RemoteApp}
    for app in VersionedDoc.view('app_manager/applications', startkey=[domain], endkey=[domain, '']).all():
        cls = str_to_cls[app.doc_type]
        applications.append(cls.wrap(app.to_json()))
    app = module = form = None
    if app_id:
        app = get_app(domain, app_id)
    elif applications and select_first:
        app = applications[0]
    if module_id:
        module = app.get_module(module_id)
    elif app and app.doc_type == "Application" and app.modules and select_first:
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

    if app:
        saved_apps = (app.__class__).view('app_manager/applications',
            startkey=[domain, app_id, {}],
            endkey=[domain, app_id],
            descending=True
        ).all()
    else:
        saved_apps = []

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
        'langs': [lang] + (app.langs if app else [])    ,
        'lang': lang,

        'saved_apps': saved_apps,
    }
@login_and_domain_required
def forms(req, domain, app_id='', module_id='', form_id='', template='app_manager/forms.html'):
    error = req.GET.get('error', '')
    context = _forms_context(req, domain, app_id, module_id, form_id)
    app = context['app']
    if not app and context['applications']:
        app_id = context['applications'][0]._id
        return back_to_main(**locals())
    if app and app.copy_of:
        raise Http404
    force_edit = False
    if (not context['applications']) or (app and app.doc_type == "Application" and not app.modules):
        edit = True
        force_edit = True
    context.update({
        'force_edit': force_edit,
        'error':error,
        'app': app,
    })
    response = render_to_response(req, template, context)
    response.set_cookie('lang', context['lang'])
    return response

@login_and_domain_required
def form_view(req, domain, app_id, module_id, form_id, template="app_manager/form_view.html"):
    return forms(req, domain, app_id, module_id, form_id, template=template)

@login_and_domain_required
def module_view(req, domain, app_id, module_id, template='app_manager/module_view.html'):
    return forms(req, domain, app_id, module_id, template=template)

@login_and_domain_required
def app_view(req, domain, app_id, template="app_manager/app_view.html"):
    return forms(req, domain, app_id, template=template)

@login_and_domain_required
def new_app(req, domain):
    if req.method == "POST":
        form = NewAppForm(req.POST)
        if form.is_valid():
            cd = form.cleaned_data
            name = cd['name']
            if " (remote)" == name[-9:]:
                name = name[:-9]
                cls = RemoteApp
            else:
                cls = Application


            all_apps = Application.view('app_manager/applications', key=[domain]).all()
            if name in [a.name.get(lang, "") for a in all_apps]:
                error="app_exists"
            else:
                app = cls.new_app(domain, name)
                app.save()
                return HttpResponseRedirect(
                    reverse('corehq.apps.app_manager.views.app_view', args=[domain, app['_id']])
                    + "?edit=true"
                )

        else:
            error="app_form_invalid"
    else:
        error="wtf"
    return HttpResponseRedirect(
        reverse('corehq.apps.app_manager.views.forms', args=[domain])
        + "?edit=true" + ";error=%s" % error
    )

@login_and_domain_required
def new_module(req, domain, app_id):
    app = get_app(domain, app_id)
    lang = req.COOKIES.get('lang', app.langs[0])
    if req.method == "POST":
        form = NewModuleForm(req.POST)
        if form.is_valid():
            cd = form.cleaned_data
            name = cd['name']
            if name in [m['name'].get(lang, "") for m in app.modules]:
                error = "module_exists"
            else:
                module = app.new_module(name, lang)
                app.save()
                return HttpResponseRedirect(
                    reverse('corehq.apps.app_manager.views.module_view', args=[domain, app_id, module.id])
                    + "?edit=true"
                )
        else:
            error = "module_form_invalid"
    else:
        error = "wtf"

    return HttpResponseRedirect(
        reverse('corehq.apps.app_manager.views.app_view', args=[domain, app_id])
        + "?edit=true" + ";error=%s" % error
    )

@login_and_domain_required
def new_form(req, domain, app_id, module_id, template="app_manager/new_form.html"):
    app = get_app(domain, app_id)
    lang = req.COOKIES.get('lang', app.langs[0])
    if req.method == "POST":
        form = NewXFormForm(req.POST, req.FILES)

        if form.is_valid():
            cd = form.cleaned_data
            name = cd['name']
            attachment = cd['file']
            form = app.new_form(module_id, name, attachment, lang)
            app.save()
            return HttpResponseRedirect(
                reverse('corehq.apps.app_manager.views.form_view', args=[domain, app_id, module_id, form.id])
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

@login_and_domain_required
def delete_app(req, domain, app_id):
    get_app(domain, app_id).delete()
    return HttpResponseRedirect(
        reverse('corehq.apps.app_manager.views.forms', args=[domain])
        + "?edit=true"
    )

@login_and_domain_required
def delete_module(req, domain, app_id, module_id):
    app = get_app(domain, app_id)
    app.delete_module(module_id)
    app.save()
    return HttpResponseRedirect(
        reverse('corehq.apps.app_manager.views.app_view', args=[domain, app_id])
        + "?edit=true"
    )

@login_and_domain_required
def delete_form(req, domain, app_id, module_id, form_id):
    app = get_app(domain, app_id)
    app.delete_form(module_id, form_id)
    app.save()
    return HttpResponseRedirect(
        reverse('corehq.apps.app_manager.views.app_view', args=[domain, app_id])
        + "?edit=true"
    )

@login_and_domain_required
def edit_module_attr(req, domain, app_id, module_id, attr):

    if req.method == "POST":
        app = get_app(domain, app_id)
        module = app.get_module(module_id)
        lang = req.COOKIES.get('lang', app.langs[0])
        if   "case_type" == attr:
            case_type = req.POST.get("case_type", None)
            module.case_type = case_type
        elif ("name", "case_name", "ref_name").__contains__(attr):
            name = req.POST.get(attr, None)
            module[attr][lang] = name
        app.save()
    return HttpResponseRedirect(
        reverse('corehq.apps.app_manager.views.module_view', args=[domain, app_id, module_id])
        + "?edit=true"
    )
@login_and_domain_required
def edit_module_detail(req, domain, app_id, module_id):
    if req.method == "POST":
        column_id = int(req.POST.get('column_id', -1))
        detail_type = req.POST.get('detail_type', '')
        assert(detail_type in DETAIL_TYPES)

        column = dict((key, req.POST[key]) for key in ('header', 'model', 'field', 'format', 'enum'))
        app = get_app(domain, app_id)
        module = app.get_module(module_id)
        lang = req.COOKIES.get('lang', app.langs[0])


        def _enum_to_dict(enum):
            if not enum:
                return {}
            answ = {}
            for s in enum.split(','):
                key, val = (x.strip() for x in s.strip().split('='))
                answ[key] = {}
                answ[key][lang] = val
            return answ

        column['enum'] = _enum_to_dict(column['enum'])
        column['header'] = {lang: column['header']}
        column = DetailColumn.wrap(column)
        detail = app.get_module(module_id).get_detail(detail_type)

        if(column_id == -1):
            detail.append_column(column)
        else:
            detail.update_column(column_id, column)
        app.save()

    return HttpResponseRedirect(
        reverse('corehq.apps.app_manager.views.module_view', args=[domain, app_id, module_id])
        + "?edit=true"
    )

@login_and_domain_required
def delete_module_detail(req, domain, app_id, module_id):
    if req.method == "POST":
        column_id = int(req.POST['column_id'])
        detail_type = req.POST['detail_type']
        app = get_app(domain, app_id)
        module = app.get_module(module_id)
        module.get_detail(detail_type).delete_column(column_id)
        app.save()
    return back_to_main(edit=True, **locals())

@login_and_domain_required
def edit_form_attr(req, domain, app_id, module_id, form_id, attr):
    if req.method == "POST":
        app = get_app(domain, app_id)
        form = app.get_module(module_id).get_form(form_id)
        lang = req.COOKIES.get('lang', app.langs[0])

        if   "requires" == attr:
            requires = req.POST['requires']
            form.requires = requires
        elif "name" == attr:
            name = req.POST['name']
            form.name[lang] = name
        elif "xform" == attr:
            xform = req.FILES['xform']
            xform = XForm.new_xform(domain, xform)
            form.xform_id = xform._id
            form.xmlns = xform.xmlns
        elif "show_count" == attr:
            show_count = req.POST['show_count']
            form.show_count = True if show_count == "True" else False
        app.save()
    return back_to_main(edit=True, **locals())

@login_and_domain_required
def edit_app_lang(req, domain, app_id):
    if req.method == "POST":
        lang = req.POST['lang']
        lang_id = int(req.POST.get('lang_id', -1))
        app = get_app(domain, app_id)
        if lang_id == -1:
            app.langs.append(lang)
        else:
            app.langs[lang_id] = lang
        app.save()
    return back_to_main(edit=True, **locals())

@login_and_domain_required
def delete_app_lang(req, domain, app_id):
    if req.method == "POST":
        lang_id = int(req.POST['lang_id'])
        app = get_app(domain, app_id)
        del app.langs[lang_id]
        app.save()
    return back_to_main(edit=True, **locals())

@login_and_domain_required
def edit_app_attr(req, domain, app_id, attr):
    if req.method == "POST":
        app = get_app(domain, app_id)
        lang = req.COOKIES.get('lang', app.langs[0])
        if   "suite_url" == attr:
            if app.doc_type not in ("RemoteApp",):
                raise Exception("App type %s does not support suite urls" % app.doc_type)
            app['suite_url'] = req.POST['suite_url']
            app.save()
    return back_to_main(edit=True, **locals())


@login_and_domain_required
def swap(req, domain, app_id, key):
    if req.method == "POST":
        app = get_app(domain, app_id)
        i, j = (int(x) for x in (req.POST['to'], req.POST['from']))
        assert(i < j)
        if   "forms" == key:
            module_id = int(req.POST['module_id'])
            app.swap_forms(module_id, i, j)
        elif "modules" == key:
            app.swap_modules(i, j)
        elif "detail" == key:
            module_id = int(req.POST['module_id'])
            app.swap_detail_columns(module_id, req.POST['detail_type'], i, j)
        elif "langs" == key:
            app.swap_langs(i, j)
        app.save()
    return back_to_main(edit=True, **locals())

def _url_base():
    return URL_BASE

def _check_domain_app(domain, app_id):
    get_app(domain, app_id)

def download_profile(req, domain, app_id, template='app_manager/profile.xml'):
    app = get_app(domain, app_id)
    url_base = _url_base()
    post_url = url_base + reverse('corehq.apps.receiver.views.post', args=[domain])
    if 'suite_url' in app and app['suite_url']:
        suite_url = app['suite_url']
    else:
        suite_url = url_base + reverse('corehq.apps.app_manager.views.download_suite', args=[domain, app_id])
    return render_to_response(req, template, {
        'app': app,
        'suite_url': suite_url,
        'post_url': post_url,
        'post_test_url': post_url,
    })

def download_suite(req, domain, app_id, template='app_manager/suite.xml'):
    app = get_app(domain, app_id)
    return render_to_response(req, template, {
        'app': app,
        'langs': ["default"] + app.langs
    })


def download_app_strings(req, domain, app_id, lang, template='app_manager/app_strings.txt'):
    app = get_app(domain, app_id)
    return render_to_response(req, template, {
        'app': app,
        'langs': [lang] + app.langs,
    })

def download_xform(req, domain, app_id, module_id, form_id):
    xform_id = get_app(domain, app_id).get_module(module_id).get_form(form_id)['xform_id']
    xform = XForm.get(xform_id)
    xform_xml = xform.fetch_attachment('xform.xml')
    return HttpResponse(xform_xml)

def download_jad(req, domain, app_id, template="app_manager/CommCare.jad"):
    app = get_app(domain, app_id)
    url_base = _url_base()
    if 'profile_url' in app and app['profile_url']:
        profile_url = app['profile_url']
    else:
        profile_url = url_base + reverse('corehq.apps.app_manager.views.download_profile', args=[domain, app_id])
    response = render_to_response(req, template, {
        'domain': domain,
        'app': app,
        'profile_url': profile_url,
        'jar_url': url_base + reverse('corehq.apps.app_manager.views.download_jar', args=[domain, app_id]),
    })
    response["Content-Type"] = "text/vnd.sun.j2me.app-descriptor"
    return response

def download_jar(req, domain, app_id):
    view,args,kwargs = resolve('/static/app_manager/CommCare.jar')
    response = view(req, *args, **kwargs)
    response['Content-Type'] = "application/java-archive"
    return response

#@login_and_domain_required
#def download(req, domain, app_id):
#    url_base = _url_base()
#    response = HttpResponse(mimetype="application/zip")
#    response['Content-Disposition'] = "filename=commcare_app.zip"
#    app = get_app(domain, app_id)
#    root = url_base + reverse('corehq.apps.app_manager.views.download', args=[domain, app_id])
#    paths = ["profile.xml", "suite.xml"]
#    for lang in app.langs:
#        paths.append("%s/app_strings.txt" % lang)
#    for module in app.get_modules():
#        for form in module.get_forms():
#            paths.append("m%s/f%s.xml" % (module.id, form.id))
#    print paths
#    buffer = StringIO()
#    zipper = ZipFile(buffer, 'w', ZIP_DEFLATED)
#    for path in paths:
#        print path
#        zipper.writestr(path, urlopen(root + path).read())
#    zipper.close()
#    buffer.flush()
#    response.write(buffer.getvalue())
#    buffer.close()
#    return response


@login_and_domain_required
def save_copy(req, domain, app_id):
    if req.method == "POST":
        edit = req.POST.get('edit', '') == "true"
        app = get_app(domain, app_id)
        app.save_copy()
        return back_to_main(**locals())


@login_and_domain_required
def revert_to_copy(req, domain, app_id):
    if req.method == "POST":
        app = get_app(domain, app_id)
        copy = get_app(domain, req.POST['saved_app'])
        app = app.revert_to_copy(copy)
        return back_to_main(edit=True, **locals())

@login_and_domain_required
def delete_copy(req, domain, app_id):
    if req.method == "POST":
        app = get_app(domain, app_id)
        copy = get_app(domain, req.POST['saved_app'])
        app.delete_copy(copy)
    return back_to_main(edit=True, **locals())