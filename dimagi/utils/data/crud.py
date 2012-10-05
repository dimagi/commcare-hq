from django import forms
from django.forms.util import ErrorList
from django.template.loader import render_to_string
import json
from dimagi.utils.decorators.memoized import memoized

class TabularCRUDManager(object):
    """
        Tabular Create Read Update Delete Manager
        Use this to update couchdocs from tablular view (like GenericTabularReport).
    """

    def __init__(self, document_class, document_instance=None):
        self.document_class = document_class
        self.document_instance = document_instance

    @property
    def edit_button(self):
        """
            Should output a string of html that will be the edit button.
        """
        return NotImplementedError

    @property
    def properties_in_row(self):
        """
            Return a list of properties that will show up as columns in the row that summarizes the editable
            document in the GenericTabularView.
        """
        return NotImplementedError

    @property
    def row(self):
        """
            Creates the row to be outputted in a table.
        """
        row = []
        for key in self.properties_in_row:
            col = None
            if self.document_instance:
                property = getattr(self.document_instance, key)
                col = self.format_property(key, property)
            row.append(col or "")
        row.append(self.edit_button)
        return row

    def format_property(self, key, property):
        return property

    def is_valid(self, existing=None, **kwargs):
        """
            Any validation on the CRUD form fields related to the document can go here.
        """
        return True

    def update(self, **kwargs):
        """
            Updates self.document_instance.
        """
        raise NotImplementedError

    def create(self, **kwargs):
        """
            Creates a new self.document_instance from self.document_class.
        """
        raise NotImplementedError


class BaseCRUDForm(forms.Form):
    """
        Use this form for updating couch documents that have a CRUDManager.
    """
    doc_class = None

    def __init__(self, data=None, files=None, auto_id='id_%s', prefix=None,
                 initial=None, error_class=ErrorList, label_suffix=':',
                 empty_permitted=False, doc_id=None):
        self.doc_id = doc_id
        if doc_id and data is None:
            data=self.existing_object._doc
        super(BaseCRUDForm, self).__init__(data, files, auto_id, prefix, initial,
            error_class, label_suffix, empty_permitted)

    @property
    @memoized
    def existing_object(self):
        if self.doc_id:
            return self.doc_class.get(self.doc_id)
        return None

    @property
    def crud_manager(self):
        raise NotImplementedError

    def clean(self):
        cleaned_data = super(BaseCRUDForm, self).clean()
        if not self.crud_manager.is_valid(self.existing_object, **cleaned_data):
            raise forms.ValidationError("This item already exists.")
        return cleaned_data

    def save(self):
        if self.existing_object:
            self.crud_manager.update(**self.cleaned_data)
        else:
            self.crud_manager.create(**self.cleaned_data)
        return [self.crud_manager.row]


class CRUDActionError(Exception):
    pass


class CRUDFormRequestManager(object):
    """
        How to handle the form post/get in a django view.
    """

    def __init__(self, request, form_class, form_template, doc_id=None, delete=False):
        if not issubclass(form_class, BaseCRUDForm):
            raise CRUDActionError("form_class must be a subclass of BaseCRUDForm to complete this action")
        if delete and not doc_id:
            raise CRUDActionError("A doc_id is required to perform the delete action.")
        self.request = request
        self.form_class = form_class
        self.form_template = form_template
        self.errors = list()
        self.doc_id = doc_id
        self.delete = delete
        self.success = False

    @property
    def json_response(self):
        if self.delete:
            form, result = self._delete_doc()
        elif self.request.method == 'POST':
            form, result = self._update_or_create_doc()
        else:
            form = self._get_form()
            result = []
        form_update = render_to_string(self.form_template, dict(form=form)) if form else ""
        return json.dumps(dict(
            success=self.success,
            deleted=self.delete and self.success,
            form_update=form_update,
            rows=result,
            errors=self.errors
        ))

    def _get_form(self):
        if self.request.method == 'POST' and not self.success:
            return self.form_class(self.request.POST, doc_id=self.doc_id)
        return self.form_class(doc_id=self.doc_id)

    def _update_or_create_doc(self):
        form = self._get_form()
        result = []
        if form.is_valid():
            result = form.save()
            self.success = True
            form = self._get_form()
        return form, result

    def _delete_doc(self):
        try:
            doc = self.form_class.doc_class.get(self.doc_id)
            doc.delete()
            self.success = True
            self.doc_id = None
        except Exception as e:
            self.errors.append("Could not delete document with id %s due to error: %s" % (self.doc_id, e))
        return self._get_form(), []
