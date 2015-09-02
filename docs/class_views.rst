Using Class-Based Views in CommCare HQ
======================================

We should move away from function-based views in django and use class-based views instead.
The goal of this section is to point out the infrastructure we've already set up to
keep the UI standardized.

The Base Classes
----------------

There are two styles of pages in CommCare HQ. One page is centered (e.g. registration,
org settings or the list of projects). The other is a two column, with the left gray column
acting as navigation and the right column displaying the primary content (pages under major sections
like reports).

A Basic (Centered) Page
^^^^^^^^^^^^^^^^^^^^^^^

To get started, subclass `BasePageView` in `corehq.apps.hqwebapp.views`. `BasePageView` is a subclass
of django's `TemplateView`.

.. code-block:: python

    class MyCenteredPage(BasePageView):
        urlname = 'my_centered_page'
        page_title = "My Centered Page"
        template_name = 'path/to/template.html'

        @property
        def page_url(self):
            # often this looks like:
            return reverse(self.urlname)

        @property
        def page_context(self):
            # You want to do as little logic here.
            # Better to divvy up logical parts of your view in other instance methods or properties
            # to keep things clean.
            # You can also do stuff in the get() and post() methods.
            return {
                'some_property': self.compute_my_property(),
                'my_form': self.centered_form,
            }

`urlname`
    This is what django urls uses to identify your page

`page_title`
    This text will show up in the `<title>` tag of your template. It will also show up in the
    primary heading of your template.

    If you want to do use a property in that title that would only be available after your
    page is instantiated, you should override:

    .. code-block:: python

        @property
        def page_name(self):
            return mark_safe("This is a page for <strong>%s</strong>" % self.kitten.name)

    `page_name` will not show up in the `<title>` tags, as you can include html in this name.

`template_name`
    Your template should extend `style/bootstrap2/base_page.html`

    It might look something like:

    .. code-block:: html

        {% extends 'style/bootstrap2/base_page.html' %}

        {% block js %}{{ block.super }}
            {# some javascript imports #}
        {% endblock %}

        {% block js-inline %}{{ block.super }}
            {# some inline javascript #}
        {% endblock %}

        {% block page_content %}
            My page content! Woo!
        {% endblock %}

        {% block modals %}{{ block.super }}
            {# a great place to put modals #}
        {% endblock %}


A Section (Two-Column) Page
^^^^^^^^^^^^^^^^^^^^^^^^^^^

To get started, subclass `BaseSectionPageView` in `corehq.apps.hqwebapp.views`. You should
implement all the things described in the minimal setup for `A Basic (Centered) Page`_
in addition to:

.. code-block:: python

    class MySectionPage(BaseSectionPageView):
        ...  # everything from BasePageView

        section_name = "Data"
        template_name = 'my_app/path/to/template.html'

        @property
        def section_url(self):
            return reverse('my_section_default')

.. note:: Domain Views

    If your view uses `domain`, you should subclass `BaseDomainView`. This inserts the domain
    name as into the `main_context` and adds the `login_and_domain_required` permission.
    It also implements `page_url` to assume the basic `reverse` for a page in a project:
    `reverse(self.urlname, args=[self.domain])`

`section_name`
    This shows up as the root name on the section breadcrumbs.

`template_name`
    Your template should extend `style/bootstrap2/base_section.html`

    It might look something like:

    .. code-block:: html

        {% extends 'style/bootstrap2/base_section.html' %}

        {% block js %}{{ block.super }}
            {# some javascript imports #}
        {% endblock %}

        {% block js-inline %}{{ block.super }}
            {# some inline javascript #}
        {% endblock %}

        {% block main_column %}
            My page content! Woo!
        {% endblock %}

        {% block modals %}{{ block.super }}
            {# a great place to put modals #}
        {% endblock %}

.. note:: Organizing Section Templates

    Currently, the practice is to extend `style/bootstrap2/base_section.html` in a base template for
    your section (e.g. `users/base_template.html`) and your section page will then extend
    its section's base template.


Adding to Urlpatterns
---------------------

Your `urlpatterns` should look something like:

.. code-block:: python

    urlpatterns = patterns(
        'corehq.apps.my_app.views',
        ...,
        url(r'^my/page/path/$', MyCenteredPage.as_view(), name=MyCenteredPage.urlname),
    )


Hierarchy
---------

If you have a hierarchy of pages, you can implement the following in your class:

.. code-block:: python

    class MyCenteredPage(BasePageView):
        ...

        @property
        def parent_pages(self):
            # This will show up in breadcrumbs as MyParentPage > MyNextPage > MyCenteredPage
            return [
                {
                    'title': MyParentPage.page_title,
                    'url': reverse(MyParentPage.urlname),
                },
                {
                    'title': MyNextPage.page_title,
                    'url': reverse(MyNextPage.urlname),
                },
            ]


If you have a hierarchy of pages, it might be wise to implement a `BaseParentPageView` or
`Base<InsertSectionName>View` that extends the `main_context` property. That way all of the
pages in that section have access to the section's context. All page-specific context should
go in `page_context`.

.. code-block:: python

    class BaseKittenSectionView(BaseSectionPageView):

        @property
        def main_context(self):
            main_context = super(BaseParentView, self).main_context
            main_context.update({
                'kitten': self.kitten,
            })
            return main_context


Permissions
-----------

To add permissions decorators to a class-based view, you need to decorate the `dispatch`
instance method.

.. code-block:: python

    class MySectionPage(BaseSectionPageView):
        ...

        @method_decorator(can_edit)
        def dispatch(self, request, *args, **kwargs)
            return super(MySectionPage, self).dispatch(request, *args, **kwargs)


GETs and POSTs (and other http methods)
---------------------------------------

Depending on the type of request, you might want to do different things.

.. code-block:: python

    class MySectionPage(BaseSectionPageView):
        ...

        def get(self, request, *args, **kwargs):
            # do stuff related to GET here...
            return super(MySectionPage, self).get(request, *args, **kwargs)

        def post(self, request, *args, **kwargs):
            # do stuff related to post here...
            return self.get(request, *args, **kwargs)  # or any other HttpResponse object


Limiting HTTP Methods
^^^^^^^^^^^^^^^^^^^^^

If you want to limit the HTTP request types to just GET or POST, you just have to override the
`http_method_names` class property:

.. code-block:: python

    class MySectionPage(BaseSectionPageView):
        ...
        http_method_names = ['post']

.. note:: Other Allowed Methods

    `put`, `delete`, `head`, `options`, and `trace` are all allowed methods by default.

