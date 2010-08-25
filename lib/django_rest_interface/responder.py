"""
MORE INFO AT: http://code.google.com/p/django-rest-interface/wiki/RestifyDjango
Data format classes ("responders") that can be plugged 
into model_resource.ModelResource and determine how
the objects of a ModelResource instance are rendered
(e.g. serialized to XML, rendered by templates, ...).
"""
from django.core import serializers
from django.core.handlers.wsgi import STATUS_CODE_TEXT
from django.core.paginator import QuerySetPaginator, InvalidPage
# the correct paginator for Model objects is the QuerySetPaginator,
# not the Paginator! (see Django doc)
from django.core.xheaders import populate_xheaders
from django import forms
from django.http import Http404, HttpResponse
from django.forms.util import ErrorDict
from django.shortcuts import render_to_response
from django.template import loader, RequestContext
from django.utils import simplejson
from django.utils.xmlutils import SimplerXMLGenerator
from django.views.generic.simple import direct_to_template

class SerializeResponder(object):
    """
    Class for all data formats that are possible
    with Django's serializer framework.
    """
    def __init__(self, format, mimetype=None, paginate_by=None, allow_empty=False):
        """
        format:
            may be every format that works with Django's serializer
            framework. By default: xml, python, json, (yaml).
        mimetype:
            if the default None is not changed, any HttpResponse calls 
            use settings.DEFAULT_CONTENT_TYPE and settings.DEFAULT_CHARSET
        paginate_by:
            Number of elements per page. Default: All elements.
        """
        self.format = format
        self.mimetype = mimetype
        self.paginate_by = paginate_by
        self.allow_empty = allow_empty
        self.expose_fields = []
        
    def render(self, object_list):
        """
        Serializes a queryset to the format specified in
        self.format.
        """
        # Hide unexposed fields
        hidden_fields = []
        for obj in list(object_list):
            for field in obj._meta.fields:
                if not field.name in self.expose_fields and field.serialize:
                    field.serialize = False
                    hidden_fields.append(field)
        response = serializers.serialize(self.format, object_list)
        # Show unexposed fields again
        for field in hidden_fields:
            field.serialize = True
        return response
    
    def element(self, request, elem):
        """
        Renders single model objects to HttpResponse.
        """
        return HttpResponse(self.render([elem]), self.mimetype)
    
    def error(self, request, status_code, error_dict=None):
        """
        Handles errors in a RESTful way.
        - appropriate status code
        - appropriate mimetype
        - human-readable error message
        """
        if not error_dict:
            error_dict = ErrorDict()
        response = HttpResponse(mimetype = self.mimetype)
        response.write('%d %s' % (status_code, STATUS_CODE_TEXT[status_code]))
        if error_dict:
            response.write('\n\nErrors:\n')
            response.write(error_dict.as_text())
        response.status_code = status_code
        return response
    
    def list(self, request, queryset, page=None):
        """
        Renders a list of model objects to HttpResponse.
        """
        if self.paginate_by:
            paginator = QuerySetPaginator(queryset, self.paginate_by)
            if not page:
                page = request.GET.get('page', 1)
            try:
                page = int(page)
                object_list = paginator.page(page).object_list
            except (InvalidPage, ValueError):
                if page == 1 and self.allow_empty:
                    object_list = []
                else:
                    return self.error(request, 404)
        else:
            object_list = list(queryset)
        return HttpResponse(self.render(object_list), self.mimetype)
    
class JSONResponder(SerializeResponder):
    """
    JSON data format class.
    """
    def __init__(self, paginate_by=None, allow_empty=False):
        SerializeResponder.__init__(self, 'json', 'application/json',
                    paginate_by=paginate_by, allow_empty=allow_empty)

    def error(self, request, status_code, error_dict=None):
        """
        Return JSON error response that includes a human readable error
        message, application-specific errors and a machine readable
        status code.
        """
        if not error_dict:
            error_dict = ErrorDict()
        response = HttpResponse(mimetype = self.mimetype)
        response.status_code = status_code
        response_dict = {
            "error-message" : '%d %s' % (status_code, STATUS_CODE_TEXT[status_code]),
            "status-code" : status_code,
            "model-errors" : error_dict.as_ul()
        }
        simplejson.dump(response_dict, response)
        return response

class XMLResponder(SerializeResponder):
    """
    XML data format class.
    """
    def __init__(self, paginate_by=None, allow_empty=False):
        SerializeResponder.__init__(self, 'xml', 'application/xml',
                    paginate_by=paginate_by, allow_empty=allow_empty)

    def error(self, request, status_code, error_dict=None):
        """
        Return XML error response that includes a human readable error
        message, application-specific errors and a machine readable
        status code.
        """
        from django.conf import settings
        if not error_dict:
            error_dict = ErrorDict()
        response = HttpResponse(mimetype = self.mimetype)
        response.status_code = status_code
        xml = SimplerXMLGenerator(response, settings.DEFAULT_CHARSET)
        xml.startDocument()
        xml.startElement("django-error", {})
        xml.addQuickElement(name="error-message", contents='%d %s' % (status_code, STATUS_CODE_TEXT[status_code]))
        xml.addQuickElement(name="status-code", contents=str(status_code))
        if error_dict:
            xml.startElement("model-errors", {})
            for (model_field, errors) in error_dict.items():
                for error in errors:
                    xml.addQuickElement(name=model_field, contents=error)
            xml.endElement("model-errors")
        xml.endElement("django-error")
        xml.endDocument()
        return response

class TemplateResponder(object):
    """
    Data format class that uses templates (similar to Django's
    generic views).
    """
    def __init__(self, template_dir, paginate_by=None, template_loader=loader,
                 extra_context=None, allow_empty=False, context_processors=None,
                 template_object_name='object', mimetype=None):
        self.template_dir = template_dir
        self.paginate_by = paginate_by
        self.template_loader = template_loader
        if not extra_context:
            extra_context = {}
        for key, value in extra_context.items():
            if callable(value):
                extra_context[key] = value()
        self.extra_context = extra_context
        self.allow_empty = allow_empty
        self.context_processors = context_processors
        self.template_object_name = template_object_name
        self.mimetype = mimetype
        self.expose_fields = None # Set by Collection.__init__
            
    def _hide_unexposed_fields(self, obj, allowed_fields):
        """
        Remove fields from a model that should not be public.
        """
        for field in obj._meta.fields:
            if not field.name in allowed_fields and \
               not field.name + '_id' in allowed_fields:
                obj.__dict__.pop(field.name)    

    def list(self, request, queryset, page=None):
        """
        Renders a list of model objects to HttpResponse.
        """
        template_name = '%s/%s_list.html' % (self.template_dir, queryset.model._meta.module_name)
        if self.paginate_by:
            paginator = QuerySetPaginator(queryset, self.paginate_by)
            if not page:
                page = request.GET.get('page', 1)
            try:
                page = int(page)
                object_list = paginator.page(page).object_list
            except (InvalidPage, ValueError):
                if page == 1 and self.allow_empty:
                    object_list = []
                else:
                    raise Http404
            current_page = paginator.page(page)
            c = RequestContext(request, {
                '%s_list' % self.template_object_name: object_list,
                'is_paginated': paginator.num_pages > 1,
                'results_per_page': self.paginate_by,
                'has_next': current_page.has_next(),
                'has_previous': current_page.has_previous(),
                'page': page,
                'next': page + 1,
                'previous': page - 1,
                'last_on_page': current_page.end_index(),
                'first_on_page': current_page.start_index(),
                'pages': paginator.num_pages,
                'hits' : paginator.count,
            }, self.context_processors)
        else:
            object_list = queryset
            c = RequestContext(request, {
                '%s_list' % self.template_object_name: object_list,
                'is_paginated': False
            }, self.context_processors)
            if not self.allow_empty and len(queryset) == 0:
                raise Http404
        # Hide unexposed fields
        for obj in object_list:
            self._hide_unexposed_fields(obj, self.expose_fields)
        c.update(self.extra_context)        
        t = self.template_loader.get_template(template_name)
        return HttpResponse(t.render(c), mimetype=self.mimetype)

    def element(self, request, elem):
        """
        Renders single model objects to HttpResponse.
        """
        template_name = '%s/%s_detail.html' % (self.template_dir, elem._meta.module_name)
        t = self.template_loader.get_template(template_name)
        c = RequestContext(request, {
            self.template_object_name : elem,
        }, self.context_processors)
        # Hide unexposed fields
        self._hide_unexposed_fields(elem, self.expose_fields)
        c.update(self.extra_context)
        response = HttpResponse(t.render(c), mimetype=self.mimetype)
        populate_xheaders(request, response, elem.__class__, getattr(elem, elem._meta.pk.name))
        return response
    
    def error(self, request, status_code, error_dict=None):
        """
        Renders error template (template name: error status code).
        """
        if not error_dict:
            error_dict = ErrorDict()
        response = direct_to_template(request, 
            template = '%s/%s.html' % (self.template_dir, str(status_code)),
            extra_context = { 'errors' : error_dict },
            mimetype = self.mimetype)
        response.status_code = status_code
        return response
    
    def create_form(self, request, queryset, form_class):
        """
        Render form for creation of new collection entry.
        """
        ResourceForm = forms.form_for_model(queryset.model, form=form_class)
        if request.POST:
            form = ResourceForm(request.POST)
        else:
            form = ResourceForm()
        template_name = '%s/%s_form.html' % (self.template_dir, queryset.model._meta.module_name)
        return render_to_response(template_name, {'form':form})

    def update_form(self, request, pk, queryset, form_class):
        """
        Render edit form for single entry.
        """
        # Remove queryset cache by cloning the queryset
        queryset = queryset._clone()
        elem = queryset.get(**{queryset.model._meta.pk.name : pk})
        ResourceForm = forms.form_for_instance(elem, form=form_class)
        if request.PUT:
            form = ResourceForm(request.PUT)
        else:
            form = ResourceForm()
        template_name = '%s/%s_form.html' % (self.template_dir, elem._meta.module_name)
        return render_to_response(template_name, 
                {'form':form, 'update':True, self.template_object_name:elem})
