Internationalization
====================

This page contains the most common techniques needed for managing CommCare HQ
localization strings. For more comprehensive information, consult the
`Django Docs translations page <https://docs.djangoproject.com/en/dev/topics/i18n/translation/>`_
or `this helpful blog post <http://blog.bessas.me/post/65775299341/using-gettext-in-django>`_.


Tagging strings in views
------------------------

**TL;DR**: ``ugettext`` should be used in code that will be run per-request.
``ugettext_lazy`` should be used in code that is run at module import.

The management command ``makemessages`` pulls out strings marked for
translation so they can be translated via transifex.  All three ugettext
functions mark strings for translation.  The actual translation is performed
separately.  This is where the ugettext functions differ.

* ``ugettext``: The function immediately returns the translation for the
  currently selected language.
* ``ugettext_lazy``: The function converts the string to a translation
  "promise" object.  This is later coerced to a string when rendering a
  template or otherwise forcing the promise.
* ``ugettext_noop``: This function only marks a string as translation string,
  it does not have any other effect; that is, it always returns the string
  itself. This should be considered an advanced tool and generally avoided.
  It could be useful if you need access to both the translated and untranslated
  strings.


The most common case is just wrapping text with ugettext.

.. code-block:: python

    from django.utils.translation import ugettext as _

    def my_view(request):
        messages.success(request, _("Welcome!"))


Typically when code is run as a result of a module being imported, there is
not yet a user whose locale can be used for translations, so it must be
delayed. This is where `ugettext_lazy` comes in.  It will mark a string for
translation, but delay the actual translation as long as possible.

.. code-block:: python

    class MyAccountSettingsView(BaseMyAccountView):
        urlname = 'my_account_settings'
        page_title = ugettext_lazy("My Information")
        template_name = 'settings/edit_my_account.html'

When variables are needed in the middle of translated strings, interpolation
can be used as normal. However, named variables should be used to ensure
that the translator has enough context.

.. code-block:: python

    message = _("User '{user}' has successfully been {action}.").format(
        user=user.raw_username,
        action=_("Un-Archived") if user.is_active else _("Archived"),
    )

This ends up in the translations file as::

    msgid "User '{user}' has successfully been {action}."

Using ``ugettext_lazy``
^^^^^^^^^^^^^^^^^^^^^^^

The `ugettext_lazy` method will work in the majority of translation situations.
It flags the string for translation but does not translate it until it is
rendered for display. If the string needs to be immediately used or
manipulated by other methods, this might not work.

When using the value immediately, there is no reason to do lazy translation.

.. code-block:: python

    return HttpResponse(ugettext("An error was encountered."))


It is easy to forget to translate form field names, as Django normally builds
nice looking text for you. When writing forms, make sure to specify labels with
a translation flagged value. These will need to be done with `ugettext_lazy`.

.. code-block:: python

    class BaseUserInfoForm(forms.Form):
        first_name = forms.CharField(label=ugettext_lazy('First Name'), max_length=50, required=False)
        last_name = forms.CharField(label=ugettext_lazy('Last Name'), max_length=50, required=False)


``ugettext_lazy``, a cautionary tale
************************************

``ugettext_lazy`` does not return a string.  This can cause complications.

When using methods to manipulate a string, lazy translated strings will not
work properly.

.. code-block:: python

    group_name = ugettext("mobile workers")
    return group_name.upper()

Converting ``ugettext_lazy`` objects to json will crash.  You should use
``dimagi.utils.web.json_handler`` to properly coerce it to a string.

.. code-block:: python

    >>> import json
    >>> from django.utils.translation import ugettext_lazy
    >>> json.dumps({"message": ugettext_lazy("Hello!")})
    TypeError: <django.utils.functional.__proxy__ object at 0x7fb50766f3d0> is not JSON serializable
    >>> from dimagi.utils.web import json_handler
    >>> json.dumps({"message": ugettext_lazy("Hello!")}, default=json_handler)
    '{"message": "Hello!"}'


Tagging strings in template files
---------------------------------

There are two ways translations get tagged in templates.

For simple and short plain text strings, use the `trans` template tag.

.. code-block:: django

    {% trans "Welcome to CommCare HQ" %}

More complex strings (requiring interpolation, variable usage or those that
span multiple lines) can make use of the `blocktrans` tag.

If you need to access a variable from the page context:

.. code-block:: django

    {% blocktrans %}This string will have {{ value }} inside.{% endblocktrans %}

If you need to make use of an expression in the translation:

.. code-block:: django

    {% blocktrans with amount=article.price %}
        That will cost $ {{ amount }}.
    {% endblocktrans %}

This same syntax can also be used with template filters:

.. code-block:: django

    {% blocktrans with myvar=value|filter %}
        This will have {{ myvar }} inside.
    {% endblocktrans %}

In general, you want to avoid including HTML in translations. This will make it
easier for the translator to understand and manipulate the text. However, you
can't always break up the string in a way that gives the translator enough
context to accurately do the translation. In that case, HTML inside the
translation tags will still be accepted.

.. code-block:: django

    {% blocktrans %}
        Manage Mobile Workers <small>for CommCare Mobile and
        CommCare HQ Reports</small>
    {% endblocktrans %}

Text passed as constant strings to template block tag also needs to be translated.
This is most often the case in CommCare with forms.

.. code-block:: django

    {% bootstrap_fieldset form _("Specify New Password") %}

Keeping translations up to date
-------------------------------

Once a string has been added to the code, we can update the .po file by
running `makemessages`.

To do this for all langauges::

        $ django-admin.py makemessages --all

It will be quicker for testing during development to only build one language::

        $ django-admin.py makemessages -l fra

After this command has run, your .po files will be up to date. To have content
in this file show up on the website you still need to compile the strings.

.. code-block:: python

        $ django-admin.py compilemessages

You may notice at this point that not all tagged strings with an associated
translation in the .po shows up translated. That could be because Django made
a guess on the translated value and marked the string as fuzzy. Any string
marked fuzzy will not be displayed and is an indication to the translator to
double check this.

Example::

        #: corehq/__init__.py:103
        #, fuzzy
        msgid "Export Data"
        msgstr "Exporter des cas"
