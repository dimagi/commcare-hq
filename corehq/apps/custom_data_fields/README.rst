Custom Data Fields
==================

This module provides tools for defining a custom data schema per domain for
a given entity type, such as User, Product, or Location.


Editing the model
-----------------

``SQLCustomDataFieldsDefinition``
    This is a SQL model describing a particular schema.  It lists the
    entity type, but aside from that is completely generic - there are no
    special functions here for *Custom User Data*, for example.

``CustomDataModelMixin``
    Each entity type must provide a subclass of this mixin to provide the
    interface for editing the ``SQLCustomDataFieldsDefinition``.  This
    subclass handles permissions and integration with the rest of that
    entity's section of HQ.

    For an example subclass, check out
    ``corehq.apps.users.views.mobile.custom_data_field.UserFieldsView``

    Currently, this view is passed to the generic components as a config
    object for the entity type.  We hope to split this out into a separate
    config class at some point.

``CustomDataFieldsForm``
    This is initialized by ``CustomDataModelMixin`` and shouldn't need to
    be accessed directly.  It handles it's own rendering.


Editing data for a particular entity
------------------------------------

``CustomDataEditor``
    A tool for editing the data for a particular entity, like an individual
    user.  This is intented to be used by composition.  For an example use
    case, check out
    ``corehq.apps.users.views.mobile.users.EditCommCareUserView``
    The *edit entity* view can have, for example, an instance of this
    Editor - ``custom_data`` - which will provide a form to be passed to
    the template.  The template need only include::

        {% if data_fields_form.fields %}
            {% crispy data_fields_form %}
        {% endif %}

    When handling the form submission on ``POST``, you should also call
    ``custom_data.is_valid()`` when validating the main form, and use
    ``custom_data.get_data_to_save()`` to update the custom data for that
    object before saving it.


Export and Bulk Upload
----------------------

This module does not alter the way data is stored on the individual
entities, so export should **Just Work**.

For upload, this module provides a validator accessible via the subclass of
``CustomDataModelMixin`` described above.  For example::

    custom_data_validator = UserFieldsView.get_validator(domain)

This ``custom_data_validator`` should then be passed the custom data for
each entity being uploaded, and it will verify that the data matches the
schema.  It will return either an error message or an empty string.

.. code-block:: python

    error = custom_data_validator(data)
    if error:
        raise UserUploadError(error)


Setting up a new entity type
----------------------------

To add a schema to custom data for an entiy, you need to do the following:

# Provide a subclass of ``CustomDataModelMixin`` specific to that entity
type.
# Add that view to the appropriate ``urls.py`` and to the site map in
``corehq.apps.hqwebapp.models``.  You should have available
``UserFieldsView.page_name()`` and ``UserFieldsView.urlname`` for this.
# Initialize and use the ``CustomDataEditor`` in the create and edit views
for that entity (and their templates).
# Use the *custom data validator* on bulk upload.
# Make a management command to bootstrap the custom data fields for
existing domains.  This should be run on the inital deploy.  You can
probably just start with a copypasta of one of the management commands in
this module.
