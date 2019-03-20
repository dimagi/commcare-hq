Forms in HQ
===========

See the `HQ Style Guide <style_guide_forms>`_ for guidance on form UI, whether you're creating a custom HTML form or using crispy forms.

.. _style_guide_forms: https://www.commcarehq.org/styleguide/organisms/#organisms-forms
.. _tag_csrf_example: https://github.com/dimagi/commcare-hq/pull/9580/files#diff-b707708b04006cb99be5064dedbc8240R41
.. _ajax_csrf_example: https://github.com/dimagi/commcare-hq/commit/75c4fd0c638c2c79c8a1f765b70b1ac4709b043a#diff-3cfc511ef8ce8d4f15a3b64d1a113d26R125
.. _js_csrf_example_1: https://github.com/dimagi/commcare-hq/commit/a3964b2f2f1f2839df1516934b66d11dbc90faaf#diff-8380c7394c4bb525b5a02ebabc97e08fR198
.. _js_csrf_example_2: https://github.com/dimagi/commcare-hq/commit/fadf34936a4fabdf92e2e14503d39f1efb502aa2#diff-88a89488da4f667449d6a54763ab905aR9
.. _inline_csrf_example: https://github.com/dimagi/commcare-hq/commit/b12e0457b8e3b5c3accd5ef9f57a90b3018c7828#diff-597545574657c656fd164ce865186edaR1158
.. _csrf_exempt_example: https://github.com/dimagi/commcare-hq/pull/9736/files#diff-a8527f8793e60d01dedc1bc05c822d76R174
.. _django_csrf: https://docs.djangoproject.com/en/1.8/ref/csrf/

Making forms CSRF safe
----------------------

HQ is protected against cross site request forgery attacks i.e. if a `POST/PUT/DELETE` request doesn't pass csrf token to corresponding View, the View will reject those requests with a 403 response. All HTML forms and AJAX calls that make such requests should contain a csrf token to succeed. Making a form or AJAX code pass csrf token is easy and the `Django docs <django_csrf>`_ give detailed instructions on how to do so. Here we list out examples of HQ code that does that

1. If crispy form is used to render HTML form, csrf token is included automagically
2. For raw HTML form, use `{% csrf_token %}` tag in the form HTML, see tag_csrf_example_.
3. If request is made via AJAX, it will be automagically protected by `ajax_csrf_setup.js` (which is included in base bootstrap template) as long as your template is inherited from the base template. (`ajax_csrf_setup.js` overrides `$.ajaxSettings.beforeSend` to accomplish this)
4. If an AJAX call needs to override `beforeSend` itself, then the super `$.ajaxSettings.beforeSend` should be explicitly called to pass csrf token. See ajax_csrf_example_
5. If HTML form is created in Javascript using raw nodes, csrf-token node should be added to that form. See js_csrf_example_1_ and js_csrf_example_2_
6. If an inline form is generated using outside of `RequestContext` using `render_to_string` or its cousins, use `csrf_inline` custom tag. See inline_csrf_example_
7. If a View needs to be exempted from csrf check (for whatever reason, say for API), use `csrf_exampt` decorator to avoid csrf check. See csrf_exempt_example_
8. For any other special unusual case refer to `Django docs <django_csrf>`_. Essentially, either the HTTP request needs to have a csrf-token or the corresponding View should be exempted from CSRF check.
