import settings, os, sys
import logging
import traceback
import hashlib
import csv
from StringIO import StringIO
import util as xutils
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect
from django.template import RequestContext
from django.db import transaction, connection
from django.core.urlresolvers import reverse

from rapidsms.webui.utils import render_to_response

from xformmanager.util import get_unique_value
from xformmanager.forms import RegisterXForm, SubmitDataForm, FormDataGroupForm
from xformmanager.models import FormDefModel, FormDataGroup, FormDataPointer, FormDataColumn
from xformmanager.xformdef import FormDef
from xformmanager.manager import *
from xformmanager.templatetags.xform_tags import NOT_SET
from domain.decorators import login_and_domain_required
from receiver import submitprocessor
from hq.dbutil import get_column_names
from hq.models import *
from hq.utils import paginate, get_table_display_properties

from transformers.csv import UnicodeWriter
from transformers.zip import get_zipfile

from receiver.models import Attachment
from django.db.models import signals

@login_and_domain_required
@transaction.commit_manually
def remove_xform(request, form_id=None, template='confirm_delete.html'):
    context = {}
    form = get_object_or_404(FormDefModel, pk=form_id)
    if request.method == "POST":
        if request.POST["confirm_delete"]: # The user has already confirmed the deletion.
            xformmanager = XFormManager()
            xformmanager.remove_schema(form_id)
            logging.debug("Schema %s deleted ", form_id)
            #self.message_user(request, _('The %(name)s "%(obj)s" was deleted successfully.') % {'name': force_unicode(opts.verbose_name), 'obj': force_unicode(obj_display)})                    
            return HttpResponseRedirect("../register")
    context['form_name'] = form.form_display_name
    return render_to_response(request, template, context)

@login_and_domain_required
@transaction.commit_manually
def home(request, template='register_and_list_xforms.html'):
    context = {}
    if request.method == 'POST':
        if 'confirm_register' in request.POST:
            # user has already confirmed registration 
            # process saved file without bothering with validation
            try:
                formdefmodel = _register_xform(request, \
                                    request.session['schema_file'], \
                                    request.session['display_name'], \
                                    request.session['REMOTE_ADDR'], \
                                    request.session['file_size']                                
                                    )
            except Exception, e:
                logging.error(unicode(e))
                context['errors'] = unicode(e)
                transaction.rollback()
            else:
                transaction.commit()
                context['newsubmit'] = formdefmodel
        else:
            # validate and attempt to process schema
            form = RegisterXForm(request.POST, request.FILES)
            if form.is_valid():
                xformmanager = XFormManager()
                try:
                    file_name = xformmanager.save_schema_POST_to_file(\
                                request.FILES['file'], request.FILES['file'].name
                                )
                except Exception, e:
                    # typically this error is because we could not translate xform to schema
                    logging.error(unicode(e))
                    context['errors'] = unicode(e)
                    transaction.rollback()
                else:
                    is_valid, exception = xformmanager.validate_schema(file_name)
                    if is_valid:
                        try:
                            formdefmodel = _register_xform(request, file_name, \
                                               form.cleaned_data['form_display_name'], \
                                               request.META['REMOTE_ADDR'], \
                                               request.FILES['file'].size
                                               )                            
                        except Exception, e:
                            logging.error(unicode(e))
                            context['errors'] = unicode(e)
                            transaction.rollback()
                        else:
                            transaction.commit()
                            context['newsubmit'] = formdefmodel
                    else:
                        # if there are validation errors, 
                        # check the types.  If they are just warnings then
                        # redirect to the confirmation page.
                        # If they are true errors, then prevent registration
                        # but try to explain them
                        
                        logging.error(unicode(exception))
                        transaction.rollback()
                        context['errors'] = unicode(exception)
                        context['exception'] = exception
                        if isinstance(exception, FormDef.FormDefError):
                            if exception.category == FormDef.FormDefError.ERROR:
                                # this is where we get into trouble.  Display
                                # the error and then redirect home
                                return render_to_response(request, 
                                                          "xformmanager/registration_error.html", 
                                                          context)
                                
                        context['file_name'] = request.FILES['file'].name
                        request.session['schema_file'] = file_name
                        request.session['display_name'] = form.cleaned_data['form_display_name']
                        request.session['REMOTE_ADDR'] = request.META['REMOTE_ADDR']
                        request.session['file_size'] = request.FILES['file'].size
                        template='confirm_register.html'
                        return render_to_response(request, template, context)                    
            else:
                transaction.rollback()
                context['errors'] = form.errors
    
    context['upload_form'] = RegisterXForm()
    # group the formdefs by names
    context['registered_forms'] = FormDefModel.objects.all().filter(domain=request.user.selected_domain)
    context['form_groups'] = FormDefModel.get_groups(request.user.selected_domain)
    return render_to_response(request, template, context)


@login_and_domain_required
def xmlns_group(request):
    """View a group of forms for a particular xmlns."""
    xmlns = request.GET["xmlns"]
    group = FormDefModel.get_group_for_namespace(request.user.selected_domain, xmlns)
    
    data_groups = FormDataGroup.objects.filter(forms__in=group.forms).distinct()
    return render_to_response(request, "xformmanager/xmlns_group.html", 
                                  {"group": group,
                                   "data_groups": data_groups
                                   })
    
@login_and_domain_required
def xmlns_group_popup(request):
    """Popup (compact) view a group of forms for a particular xmlns.
       Used in modal dialogs."""
    xmlns = request.GET["xmlns"]
    group = FormDefModel.get_group_for_namespace(request.user.selected_domain, xmlns)
    return render_to_response(request, "xformmanager/xmlns_group_popup.html", 
                              {"group": group})

@login_and_domain_required
def manage_groups(request):
    """List and work with model-defined groups of forms."""
    data_groups = FormDataGroup.objects.all()
    return render_to_response(request, "xformmanager/list_form_data_groups.html", 
                                  {"groups": data_groups})
                                   
@login_and_domain_required
def new_form_data_group(req):
    """Create a new model-defined group of forms"""
    form_validation = None
    if req.method == "POST":
        form = FormDataGroupForm(req.POST) 
        if form.is_valid():
            if "formdefs" in req.POST:
                form_ids = req.POST.getlist("formdefs")
                if not form_ids:
                    form_validation = "You must choose at least one form!"
                else:
                    new_group = form.save(commit=False)
                    new_group.domain = req.user.selected_domain
                    # TODO: better handling of the name attribute.  
                    new_group.name = get_unique_value(FormDataGroup.objects, "name", new_group.display_name)
                    forms = [FormDefModel.objects.get(id=form_id) for form_id in form_ids]
                    new_group.save()
                    new_group.forms = forms
                    new_group.save()
                    # don't forget to do all the default column updates as well.
                    for form in forms:
                        new_group.add_form_columns(form)
                    
                    # finally update the sql view
                    new_group.update_view()
                    
                    # when done, take them to the edit page for further tweaking
                    return HttpResponseRedirect(reverse('xformmanager.views.edit_form_data_group', 
                                            kwargs={"group_id": new_group.id }))
                    
                        
            else: 
                form_validation = "You must choose at least one form!"
    else:
        form = FormDataGroupForm()
        
    all_forms = FormDefModel.objects.filter(domain=req.user.selected_domain)\
                            .order_by("target_namespace", "version")
    return render_to_response(req, "xformmanager/edit_form_data_group.html", 
                                  {"group_form": form,
                                   "all_forms": all_forms,
                                   "selected_forms": [],
                                   "form_validation": form_validation })
                                   
    
@login_and_domain_required
def form_data_group(req, group_id):
    group = get_object_or_404(FormDataGroup, id=group_id)
    items, sort_column, sort_descending, filters =\
         get_table_display_properties(req,default_sort_column = None,
                                      default_sort_descending = False)
    cursor = group.get_data(sort_column, sort_descending)
    columns = get_column_names(cursor)
    if sort_column:
        sort_index = columns.index(sort_column)
    else:
        sort_index = -1
    data = paginate(req, cursor.fetchall())
    extra_params = "&".join(['%s=%s' % (key, value)\
                             for key, value in req.GET.items()\
                             if key != "page"])
    return render_to_response(req, "xformmanager/form_data_group.html",
                              {"group": group, "columns": columns, 
                               "data": data, "sort_column": sort_column,
                               "sort_descending": sort_descending,
                               "sort_index": sort_index, 
                               "extra_params": extra_params, 
                               "editing": False })
        
@login_and_domain_required
def edit_form_data_group(req, group_id):
    """Edit a model-defined group of forms"""
    group = get_object_or_404(FormDataGroup, id=group_id)
    form_validation = None
    if req.method == "POST":
        group_form = FormDataGroupForm(req.POST, instance=group) 
        if group_form.is_valid():
            if "formdefs" in req.POST:
                form_ids = req.POST.getlist("formdefs")
                if not form_ids:
                    form_validation = "You must choose at least one form!"
                else:
                    group = group_form.save()
                    set_forms = [FormDefModel.objects.get(id=form_id) for form_id in form_ids]
                    previous_forms = group.forms.all()
                    new_forms = [form for form in set_forms if form not in previous_forms]
                    deleted_forms = [form for form in previous_forms if form not in set_forms]
                    # don't forget to do all the default column updates as well.
                    for form in new_forms:
                        group.add_form(form)
                    for form in deleted_forms:
                        group.remove_form(form)
                    
                    if new_forms or deleted_forms:
                        # finally, if anything changed update the sql view
                        group.update_view()
                    
                    # and take them back to the viewing page
                    return HttpResponseRedirect(reverse('xformmanager.views.form_data_group', 
                                                        kwargs={"group_id": group.id }))
            else: 
                form_validation = "You must choose at least one form!"
    else:
        group_form = FormDataGroupForm(instance=group)
        
    all_forms = FormDefModel.objects.filter(domain=req.user.selected_domain)\
                            .order_by("target_namespace", "version")
    selected_forms = group.forms.all()
    unused_forms = [form for form in all_forms if form not in selected_forms]
    return render_to_response(req, "xformmanager/edit_form_data_group.html", 
                                  {"group_form": group_form,
                                   "group": group,
                                   "selected_forms": selected_forms,
                                   "all_forms": unused_forms,
                                   "form_validation": form_validation })
                                   
@login_and_domain_required
def edit_form_data_group_columns(req, group_id):
    """Edit the individual columns of a form data group"""
    group = get_object_or_404(FormDataGroup, id=group_id)
    if req.method == 'POST':
        for key, value in req.POST.items():
            if key.startswith("checked_"):
                to_delete = key.replace("checked_", "")
                column = group.columns.get(name=to_delete)
                column.delete()
            elif key.startswith("select_"):
                truncated_name = key.replace("select_", "")
                form_id, column = truncated_name.split("_", 1)
                form = FormDefModel.objects.get(id=form_id)
                try:
                    column_obj = group.columns.get(name=column)
                except FormDataColumn.DoesNotExist:
                    # this likely just got deleted above or came from
                    # an out of date request.  For now just quietly 
                    # ignore it.
                    continue
                if value == NOT_SET:
                    # the only time we have to do anything here is if
                    # it was previously set.  
                    try:
                        old_field = column_obj.fields.get(form=form)
                        # we found something, better get rid of it
                        column_obj.fields.remove(old_field)
                        column_obj.save()
                    except FormDataPointer.DoesNotExist:
                        # we weren't expecting anything so nothing to do
                        pass
                else:
                    # we code these as select_<formid>_<column_name>
                    new_column = value
                    new_field = FormDataPointer.objects.get(form=form, 
                                                            column_name=new_column)
                    try:
                        old_field = column_obj.fields.get(form=form)
                        if old_field == new_field:
                            # we didn't change anything, leave it
                            pass
                        else:
                            # remove the old field from the column
                            # and add the new one
                            column_obj.fields.remove(old_field)
                            column_obj.fields.add(new_field)
                            column_obj.save()
                    except FormDataPointer.DoesNotExist:
                        # there was no previous mapping for this.  Just 
                        # add the new one
                        column_obj.fields.add(new_field)
                        column_obj.save()
            else:
                pass 
        # take them back to the viewing page
        return HttpResponseRedirect(reverse('xformmanager.views.form_data_group', 
                                        kwargs={"group_id": group.id }))
    
    return render_to_response(req, "xformmanager/edit_form_data_group_columns.html",
                              {"group": group, "editing": True }) 
                               
@login_and_domain_required
def delete_form_data_group(req, group_id):
    group = get_object_or_404(FormDataGroup, id=group_id)
    if req.method == 'POST':
        group.delete()
        return HttpResponseRedirect(reverse('xformmanager.views.home')) 
                
            
    return render_to_response(req, "xformmanager/delete_form_data_group.html",
                              {"group": group, "editing": False })
                               
        
@login_and_domain_required
def create_form_data_group_from_xmlns(req):
    """Create a form data group from a set of forms matching an xmlns"""
    xmlns = req.GET["xmlns"]
    try:
        FormDataGroup.objects.get(name=xmlns)
        # if this works, we already think we have a group.  Perhaps we should
        # ask for confirmation and allow them to recreate, but for now we'll
        # just claim this is an error.  This can be significantly UI-improved.
        error_message = "Sorry, there's already a data group created for that xmlns."
        return render_to_response(req, "500.html", {"error_message" : error_message})
    except FormDataGroup.DoesNotExist:
        # this is the correct workflow.
        forms = FormDefModel.objects.filter(domain=req.user.selected_domain, 
                                            target_namespace=xmlns)
        group = FormDataGroup.from_forms(forms, req.user.selected_domain)
        return HttpResponseRedirect(reverse('xformmanager.views.form_data_group', 
                                            kwargs={"group_id": group.id }))
                                   



def _register_xform(request, file_name, display_name, remote_addr, file_size):
    """ does the actual creation and saving of the formdef model """
    xformmanager = XFormManager()
    formdefmodel = xformmanager.create_schema_from_file(file_name, request.user.selected_domain)
    formdefmodel.submit_ip = remote_addr
    formdefmodel.bytes_received =  file_size
    formdefmodel.form_display_name = display_name                
    formdefmodel.uploaded_by = request.user
    formdefmodel.domain = request.user.selected_domain
    formdefmodel.save()
    logging.debug("xform registered")
    return formdefmodel

@login_and_domain_required
@transaction.commit_manually
def submit_data(request, formdef_id, template='submit_data.html'):
    """ A debug utility for admins to submit xml directly to a schema """ 
    context = {}
    if request.method == 'POST':
        form = SubmitDataForm(request.POST, request.FILES)        
        if form.is_valid():            
            
            xmlfile = request.FILES['file'].read()            
            checksum = hashlib.md5(xmlfile).hexdigest()
                                    
            new_submission = submitprocessor.new_submission(request.META, checksum, request.user.selected_domain)        
            submitprocessor.save_legacy_blob(new_submission, xmlfile)
            submitprocessor.handle_legacy_blob(new_submission)
            
            if new_submission == '[error]':
                logging.error("Domain Submit(): Submission error")
                context['errors'] = "Problem with submitting data"
            else:
                attachments = Attachment.objects.all().filter(submission=new_submission)
                context['submission'] = new_submission
        else:
            logging.error("Domain Submit(): Form submission error")
            context['errors'] = form.errors
    context['upload_form'] = SubmitDataForm()
    return data(request, formdef_id, template, context)

@transaction.commit_manually
def reregister_xform(request, domain_name, template='register_and_list_xforms.html'):
    # registers an xform without having a user context, for 
    # server-generated submissions
    context = {}
    if request.method == 'POST':        
        # must add_schema to storage provide first since forms are dependent upon elements 
        try:
            metadata = request.META
            domain = Domain.objects.get(name=domain_name)
            type = metadata["HTTP_SCHEMA_TYPE"]
            schema = request.raw_post_data
            xformmanager = XFormManager()
            formdefmodel = xformmanager.add_schema_manually(schema, type, domain)
        except IOError, e:
            logging.error("xformmanager.manager: " + unicode(e) )
            context['errors'] = "Could not convert xform to schema. Please verify correct xform format."
            context['upload_form'] = RegisterXForm()
            context['registered_forms'] = FormDefModel.objects.all().filter(domain__name=domain_name)
            return render_to_response(request, template, context)
        except Exception, e:
            logging.error(e)
            logging.error("Unable to write raw post data<br/>")
            logging.error("Unable to write raw post data: Exception: " + unicode(sys.exc_info()[0]) + "<br/>")
            logging.error("Unable to write raw post data: Traceback: " + unicode(sys.exc_info()[1]))
            type, value, tb = sys.exc_info()
            logging.error(unicode(type.__name__), ":", unicode(value))
            logging.error("error parsing attachments: Traceback: " + '\n'.join(traceback.format_tb(tb)))
            logging.error("Transaction rolled back")
            context['errors'] = "Unable to write raw post data" + unicode(sys.exc_info()[0]) + unicode(sys.exc_info()[1])
            transaction.rollback()                            
        else:
            formdefmodel.submit_ip = metadata['HTTP_ORIGINAL_SUBMIT_IP']
            formdefmodel.submit_time = metadata["HTTP_ORIGINAL_SUBMIT_TIME"]
            formdefmodel.date_created = metadata["HTTP_DATE_CREATED"]
            formdefmodel.bytes_received =  metadata['CONTENT_LENGTH']
            formdefmodel.form_display_name = metadata['HTTP_FORM_DISPLAY_NAME']                
            if not request.user.is_anonymous():
                formdefmodel.uploaded_by = request.user
            formdefmodel.domain = domain
            # we have the rest of the info in the metadata, but for now we
            # won't use it
            formdefmodel.save()                
            logging.debug("xform registered")
            transaction.commit()                
            context['register_success'] = True
            context['newsubmit'] = formdefmodel
            return HttpResponse("Thanks for submitting!  That worked great.  Form: %s" % formdefmodel)
    return HttpResponse("Not sure what happened but either you didn't give us a schema or something went wrong...")

def authenticate_schema(target):
    """ This decorator takes a function with 'request' and 'formdef_id' as the 
    first two arguments, and verifies that the user has permissions for that schema
    
    Redirects to no_permissions if user is not allowed to view that schema
    """
    def wrapper(request, formdef_id, *args, **kwargs):
        xform = FormDefModel.objects.get(id=formdef_id)
        if xform.domain != request.user.selected_domain:
            return HttpResponseRedirect("/no_permissions")  
        return target(request, formdef_id, *args, **kwargs)
    return wrapper

@login_and_domain_required
@authenticate_schema
def single_xform(request, formdef_id, template_name="single_xform.html"):
    context = {}    
    show_schema = False
    for item in request.GET.items():
        if item[0] == 'show_schema':
            show_schema = True
    xform = FormDefModel.objects.get(id=formdef_id)
    if show_schema:
        response = HttpResponse(mimetype='text/xml')
        fin = open(xform.xsd_file_location ,'r')
        txt = fin.read()
        fin.close()
        response.write(txt) 
        return response
    else:    
        context['xform_item'] = xform
        return render_to_response(request, template_name, context)
        
@login_and_domain_required
@authenticate_schema
def single_instance(request, formdef_id, instance_id, template_name="single_instance.html"):
    '''
       View data for a single xform instance submission.  
    '''
    xform = FormDefModel.objects.get(id=formdef_id)
    # for now, the formdef version/uiversion is equivalent to 
    # the instance version/uiversion
    data = [('XMLNS',xform.target_namespace), ('Version',xform.version), 
            ('uiVersion',xform.uiversion)]
    attach = xform.get_attachment(instance_id)
    row = xform.get_row(instance_id)
    fields = xform.get_display_columns()
    # make them a list of tuples of field, value pairs for easy iteration
    data = data + zip(fields, row)
    return render_to_response(request, template_name, {"form" : xform,
                                                       "id": instance_id,  
                                                       "data": data,
                                                       "attachment": attach })
        
@login_and_domain_required
@authenticate_schema
def single_instance_csv(request, formdef_id, instance_id):
    '''
       CSV dowload for data for a single xform instance submission.  
    '''
    # unfortunate copy pasting of the above method.   
    xform = FormDefModel.objects.get(id=formdef_id)
    row = xform.get_row(instance_id)
    fields = xform.get_display_columns()
    data = zip(fields, row)
    
    output = StringIO()
    w = UnicodeWriter(output)
    headers = ["Field", "Value"]
    w.writerow(headers)
    for row in data:
        w.writerow(row)
    output.seek(0)
    response = HttpResponse(output.read(),
                        mimetype='application/ms-excel')
    response["content-disposition"] = 'attachment; filename="%s-%s.csv"' % ( xform.form_display_name, instance_id)
    return response


@login_and_domain_required
@authenticate_schema
def export_xml(request, formdef_id):
    """
    Get a zip file containing all submissions for this schema
    """
    formdef = get_object_or_404(FormDefModel, pk=formdef_id)
    metadata = Metadata.objects.filter(formdefmodel=formdef).order_by('id')
    file_list = []
    for datum in metadata:
        file_list.append( datum.attachment.filepath )
    return get_zipfile(file_list)

@login_and_domain_required
@authenticate_schema
def plain_data(request, formdef_id, context={}, use_blacklist=True):
    '''Same as viewing the data, but pass it to a plain template.'''
    return data(request, formdef_id,'xformmanager/plain_data.html', context, use_blacklist)

    
@login_and_domain_required
@authenticate_schema
def data(request, formdef_id, template_name="data.html", context={}, use_blacklist=True):
    '''View the xform data for a particular schema.  Accepts as
       url parameters the following (with defaults specified):
       items: 25 (the number of items to paginate at a time
       page: 1 (the page you are on)
       sort_column: id (?) (the column to sort by)
       sort_descending: True (?) (the sort order of the column)
       ''' 
    # clear the context
    # (because caching on the browsers sometimes prevents this from being
    # reset properly)
    context = {}
    xform = get_object_or_404(FormDefModel, id=formdef_id)
    
    default_sort_column = "id"
    # extract params from the URL
    items, sort_column, sort_descending, filters =\
         get_table_display_properties(request,default_sort_column = default_sort_column)

    columns = xform.get_column_names()
    if not sort_column in columns:
        context["errors"] = "Sorry, we currently can't sort by the column '%s' and have sorted by the default column, '%s', instead."  %\
                        (sort_column, default_sort_column)
        sort_column = default_sort_column

    column_filters = []
    
    # pare down list of filters by only those items which are in the allowed list of 
    # columns
    clean_filters = {}
    for key, value in filters.items():
        if key in columns:
             clean_filters[key] = value
    if clean_filters:
        column_filters = [[key, "=", value] for key, value in clean_filters.items()]
        # context['filters'] will be displayed
        context['filters'] = "&".join(['%s=%s' % (key, value)
                                            for key, value
                                            in clean_filters.items()])
        
        # hacky way of making sure that the first already-filtered field
        # does not show up as a filter link - todo: clean up later
        context['filtered_by'] = clean_filters.keys()[0]
    
    if use_blacklist:
        blacklist_users = BlacklistedUser.for_domain(request.user.selected_domain)
        rows = xform.get_rows(sort_column=sort_column, sort_descending=sort_descending, 
                              blacklist=blacklist_users, column_filters=column_filters)
    else:
        rows = xform.get_rows(sort_column=sort_column, sort_descending=sort_descending, 
                              column_filters=column_filters)
    context["sort_index"] = columns.index(sort_column)
    context['columns'] = columns 
    context['form_name'] = xform.form_name
    context['xform'] = xform
    context['sort_descending'] = sort_descending
    context['data'] = paginate(request, rows, rows_per_page=items)

    # python! rebuild the query string, removing the "page" argument so it can
    # be passed on when paginating.
    context['param_string_no_page'] = "&".join(['%s=%s' % (key, value)\
                                                for key, value in request.GET.items()\
                                                if key != "page"])
    context['sort_params'] = "&".join(['%s=%s' % (key, value)
                                        for key, value in request.GET.items()\
                                        if key.startswith("sort")])
    return render_to_response(request, template_name, context)

@login_and_domain_required
@authenticate_schema
@transaction.commit_manually
def delete_data(request, formdef_id, template='confirm_multiple_delete.html'):
    context = {}
    form = get_object_or_404(FormDefModel, pk=formdef_id)
    if request.method == "POST":
        if 'instance' in request.POST:
            request.session['xform_data'] = [] 
            metadata = []
            for i in request.POST.getlist('instance'):
                # user has selected items and clicked 'delete'
                # redirect to confirmation
                if 'checked_'+ i in request.POST:
                    meta = Metadata.objects.get(formdefmodel=form, raw_data=int(i))
                    metadata.append(meta)
                    request.session['xform_data'].append(int(i))
                context['xform_data'] = metadata
        elif 'confirm_delete' in request.POST: 
            # user has confirmed deletion. Proceed.
            xformmanager = XFormManager()
            for id in request.session['xform_data']:
                xformmanager.remove_data(formdef_id, id)
            logging.debug("Instances %s of schema %s were deleted.", \
                          (unicode(request.session['xform_data']), formdef_id))
            request.session['xform_data'] = None
            return HttpResponseRedirect( reverse("xformmanager.views.data", \
                                         args=[formdef_id]) )
    else:
        request.session['xform_data'] = None
    context['form_name'] = form.form_display_name
    context['formdef_id'] = formdef_id
    return render_to_response(request, template, context)

@login_and_domain_required
@authenticate_schema
def export_csv(request, formdef_id):
    xsd = get_object_or_404( FormDefModel, pk=formdef_id)
    return format_csv(xsd.get_rows(), xsd.get_column_names(), xsd.form_name)
    
def get_csv_from_form(formdef_id, form_id=0, filter=''):
    try:
        xsd = FormDefModel.objects.get(id=formdef_id)
    except FormDefModel.DoesNotExist:
        return HttpResponseBadRequest("Schema with id %s not found." % formdef_id)
    cursor = connection.cursor()
    row_count = 0
    if form_id == 0:
        try:
            query= 'SELECT * FROM ' + xsd.form_name
            if filter: query = query + " WHERE " + filter
            query = query + ' ORDER BY id'
            cursor.execute(query)
        except Exception, e:
            return HttpResponseBadRequest(\
                "Schema %s could not be queried with query %s" % \
                ( xsd.form_name,query) )        
        rows = cursor.fetchall()
    else:
        try:
            cursor.execute("SELECT * FROM " + xsd.form_name + ' where id=%s', [form_id])
        except Exception, e:
            return HttpResponseBadRequest(\
                "Instance with id %s for schema %s not found." % (form_id,xsd.form_name) )
        rows = cursor.fetchone()
        row_count = 1
    columns = xsd.get_column_names()    
    name = xsd.form_name
    return format_csv(rows, columns, name, row_count)

