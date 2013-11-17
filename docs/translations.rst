Internationalization
====================

This page contains the most common techniques needed for managing CommCare HQ
localization strings. For more comprehensive information, consult the
`Django Docs translations page <https://docs.djangoproject.com/en/dev/topics/i18n/translation/>`_.


Tagging strings in views
------------------------

.. code-block:: python

    from django.utils.translation import ugettext as _

    def my_view(request):
        messages.success(request, _("Welcome!"))


Sometimes it isn't always so simple, for example with report or settings
section names. Two methods (`ugettext_noop` and `ugettext_lazy`) are available to mark
a string for translation but not store the translated string value. Both of these
solve the problem of 

.. code-block:: python

    class MyAccountSettingsView(BaseMyAccountView):
        urlname = 'my_account_settings'
        page_title = ugettext_lazy("My Information")
        template_name = 'settings/edit_my_account.html'

Using `ugettext_lazy`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The `ugettext_lazy` method will work in the majority of translation situations. 
It flags the string for translation but does not translate it until it is
rendered for display. If the string needs to be immediately used or
manipulated by other methods, this might not work.

When using the value immediately, there is no reason to do lazy translation.

.. code-block:: python

    return HttpResponse(ugettext("An error was encountered."))


When using methods to manipulate a string, lazy translated strings will not
work properly.

.. code-block:: python

    group_name = ugettext("mobile workers")
    return group_name.upper()




It is easy to forget to translate form field names, as Django normally builds
nice looking text for you. When writing forms, make sure to specify labels with
a translation flagged value. These will need to be done with `ugettext_lazy`.

.. code-block:: python

    class BaseUserInfoForm(forms.Form):
        first_name = forms.CharField(label=ugettext_lazy('First Name'), max_length=50, required=False)
        last_name = forms.CharField(label=ugettext_lazy('Last Name'), max_length=50, required=False)


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
