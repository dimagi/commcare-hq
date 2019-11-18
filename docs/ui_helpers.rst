UI Helpers
==========

There are a few useful UI helpers in our codebase which you should
be aware of. Save time and create consistency.


.. _paginated_crud:

Paginated CRUD View
-------------------

Use `corehq.apps.hqwebapp.views.CRUDPaginatedViewMixin` the with a `TemplateView` subclass (ideally
one that also subclasses `corehq.apps.hqwebapp.views.BasePageView` or `BaseSectionPageView`) to have
a paginated list of objects which you can create, update, or delete.


The Basic Paginated View
^^^^^^^^^^^^^^^^^^^^^^^^

In its very basic form (a simple paginated view) it should look like:

.. code-block:: python

    class PuppiesCRUDView(BaseSectionView, CRUDPaginatedViewMixin):
        # your template should extend hqwebapp/base_paginated_crud.html
        template_name = 'puppyapp/paginated_puppies.html

        # all the user-visible text
        limit_text = "puppies per page"
        empty_notification = "you have no puppies"
        loading_message = "loading_puppies"

        # required properties you must implement:

        @property
        def parameters(self):
            """
            Specify a GET or POST from an HttpRequest object.
            """
            # Usually, something like:
            return self.request.POST if self.request.method == 'POST' else self.request.GET

        @property
        def total(self):
            # How many documents are you paginating through?
            return Puppy.get_total()

        @property
        def column_names(self):
            # What will your row be displaying?
            return [
                "Name",
                "Breed",
                "Age",
            ]
            
        @property
        def page_context(self):
            # This should at least include the pagination_context that CRUDPaginatedViewMixin provides
            return self.pagination_context

        @property
        def paginated_list(self):
            """
            This should return a list (or generator object) of data formatted as follows:
            [
                {
                    'itemData': {
                        'id': <id of item>,
                        <json dict of item data for the knockout model to use>
                    },
                    'template': <knockout template id>
                }
            ]
            """
            for puppy in Puppy.get_all():
                yield {
                    'itemData': {
                        'id': puppy._id,
                        'name': puppy.name,
                        'breed': puppy.breed,
                        'age': puppy.age,
                    },
                    'template': 'base-puppy-template',
                }

        def post(self, *args, **kwargs):
            return self.paginate_crud_response

The template should use `knockout templates <http://knockoutjs.com/documentation/template-binding.html>`_
to render the data you pass back to the view. Each template will have access to
everything inside of `itemData`. Here's an example:

.. code-block:: html

    {% extends 'hqwebapp/base_paginated_crud.html' %}

    {% block pagination_templates %}
    <script type="text/html" id="base-puppy-template">
        <td data-bind="text: name"></td>
        <td data-bind="text: breed"></td>
        <td data-bind="text: age"></td>
    </script>
    {% endblock %}


Allowing Creation in your Paginated View
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you want to create data with your paginated view, you must implement the following:

.. code-block:: python

    class PuppiesCRUDView(BaseSectionView, CRUDPaginatedMixin):
        ...
        def get_create_form(self, is_blank=False):
            if self.request.method == 'POST' and not is_blank:
                return CreatePuppyForm(self.request.POST)
            return CreatePuppyForm()

        def get_create_item_data(self, create_form):
            new_puppy = create_form.get_new_puppy()
            return {
                'newItem': {
                    'id': new_puppy._id,
                    'name': new_puppy.name,
                    'breed': new_puppy.breed,
                    'age': new_puppy.age,
                },
                # you could use base-puppy-template here, but you might want to add an update button to the
                # base template.
                'template': 'new-puppy-template',
            }

The form returned in `get_create_form()` should make use of
`crispy forms <https://django-crispy-forms.readthedocs.org/en/latest/>`_.

.. code-block:: python

    from django import forms
    from crispy_forms.helper import FormHelper
    from crispy_forms.layout import Layout
    from crispy_forms.bootstrap import StrictButton, InlineField

    class CreatePuppyForm(forms.Form):
        name = forms.CharField()
        breed = forms.CharField()
        dob = forms.DateField()

        def __init__(self, *args, **kwargs):
            super(CreatePuppyForm, self).__init__(*args, **kwargs)
            self.helper = FormHelper()
            self.helper.form_style = 'inline'
            self.helper.form_show_labels = False
            self.helper.layout = Layout(
                InlineField('name'),
                InlineField('breed'),
                InlineField('dob'),
                StrictButton(
                    mark_safe('<i class="icon-plus"></i> %s' % "Create Puppy"),
                    css_class='btn-primary',
                    type='submit'
                )
            )

        def get_new_puppy(self):
            # return new Puppy
            return Puppy.create(self.cleaned_data)


Allowing Updating in your Paginated View
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you want to update data with your paginated view, you must implement the following:

.. code-block:: python

    class PuppiesCRUDView(BaseSectionView, CRUDPaginatedMixin):
        ...
        def get_update_form(self, initial_data=None):
            if self.request.method == 'POST' and self.action == 'update':
                return UpdatePuppyForm(self.request.POST)
            return UpdatePuppyForm(initial=initial_data)

        @property
        def paginated_list(self):
            for puppy in Puppy.get_all():
                yield {
                    'itemData': {
                        'id': puppy._id,
                        ...
                        # make sure you add in this line, so you can use the form in your template:
                        'updateForm': self.get_update_form_response(
                            self.get_update_form(puppy.inital_form_data)
                        ),
                    },
                    'template': 'base-puppy-template',
                }

        @property
        def column_names(self):
            return [
                ...
                # if you're adding another column to your template, be sure to give it a name here...
                _('Action'),
            ]

        def get_updated_item_data(self, update_form):
            updated_puppy = update_form.update_puppy()
            return {
                'itemData': {
                    'id': updated_puppy._id,
                    'name': updated_puppy.name,
                    'breed': updated_puppy.breed,
                    'age': updated_puppy.age,
                },
                'template': 'base-puppy-template',
            }

The `UpdatePuppyForm` should look something like:

.. code-block:: python

    class UpdatePuppyForm(CreatePuppyForm):
        item_id = forms.CharField(widget=forms.HiddenInput())

        def __init__(self, *args, **kwargs):
            super(UpdatePuppyForm, self).__init__(*args, **kwargs)
            self.helper.form_style = 'default'
            self.helper.form_show_labels = True
            self.helper.layout = Layout(
                Div(
                    Field('item_id'),
                    Field('name'),
                    Field('breed'),
                    Field('dob'),
                    css_class='modal-body'
                ),
                FormActions(
                    StrictButton(
                        "Update Puppy",
                        css_class='btn-primary',
                        type='submit',
                    ),
                    HTML('<button type="button" class="btn" data-dismiss="modal">Cancel</button>'),
                    css_class="modal-footer'
                )
            )

        def update_puppy(self):
            return Puppy.update_puppy(self.cleaned_data)

You should add the following to your `base-puppy-template` knockout template:

.. code-block:: html

    <script type="text/html" id="base-puppy-template">
        ...
        <td> <!-- actions -->
            <button type="button"
                    data-toggle="modal"
                    data-bind="
                        attr: {
                            'data-target': '#update-puppy-' + id
                        }
                    "
                    class="btn btn-primary">
                Update Puppy
            </button>

            <div class="modal hide fade"
                 data-bind="
                    attr: {
                        id: 'update-puppy-' + id
                    }
                 ">
                <div class="modal-header">
                    <button type="button" class="close" data-dismiss="modal" aria-hidden="true">&times;</button>
                    <h3>
                        Update puppy <strong data-bind="text: name"></strong>:
                    </h3>
                </div>
                <div data-bind="html: updateForm"></div>
            </div>
        </td>
    </script>


Allowing Deleting in your Paginated View
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you want to delete data with your paginated view, you should implement something like the following:

.. code-block:: python

    class PuppiesCRUDView(BaseSectionView, CRUDPaginatedMixin):
        ...

        def get_deleted_item_data(self, item_id):
            deleted_puppy = Puppy.get(item_id)
            deleted_puppy.delete()
            return {
                'itemData': {
                    'id': deleted_puppy._id,
                    ...
                },
                'template': 'deleted-puppy-template',  # don't forget to implement this!
            }

You should add the following to your `base-puppy-template` knockout template:

.. code-block:: html

    <script type="text/html" id="base-puppy-template">
        ...
        <td> <!-- actions -->
            ...
            <button type="button"
                    data-toggle="modal"
                    data-bind="
                        attr: {
                            'data-target': '#delete-puppy-' + id
                        }
                    "
                    class="btn btn-danger">
                <i class="fa fa-remove"></i> Delete Puppy
            </button>

            <div class="modal fade"
                 data-bind="
                    attr: {
                        id: 'delete-puppy-' + id
                    }
                 ">
                 <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <button type="button" class="close" data-dismiss="modal" aria-hidden="true">&times;</button>
                            <h3>
                               Delete puppy <strong data-bind="text: name"></strong>?
                            </h3>
                        </div>
                        <div class="modal-body">
                            <p class="lead">
                                Yes, delete the puppy named <strong data-bind="text: name"></strong>.
                            </p>
                        </div>
                        <div class="modal-footer">
                            <button type="button"
                                    class="btn btn-default"
                                    data-dismiss="modal">
                                Cancel
                            </button>
                            <button type="button"
                                    class="btn btn-danger delete-item-confirm"
                                    data-loading-text="Deleting Puppy...">
                                <i class="fa fa-remove"></i> Delete Puppy
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </td>
    </script>


Refreshing The Whole List Base on Update
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you want to do something that affects an item's position in the list (generally, moving it to the top), this is
the feature you want.

You implement the following method (note that a return is not expected):

.. code-block:: python

    class PuppiesCRUDView(BaseSectionView, CRUDPaginatedMixin):
        ...

        def refresh_item(self, item_id):
            # refresh the item here
            puppy = Puppy.get(item_id)
            puppy.make_default()
            puppy.save()

Add a button like this to your template:

.. code-block:: html

    <button type="button"
            class="btn refresh-list-confirm"
            data-loading-text="Making Default...">
        Make Default Puppy
    </button>

Now go on and make some CRUD paginated views!
