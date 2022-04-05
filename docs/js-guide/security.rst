Security
========

JavaScript and HTML code is subject to `XSS
attacks <https://owasp.org/www-community/attacks/xss/>`__ if user input
is not correctly sanitized.

Python
------

Read the `Django docs on
XSS <https://docs.djangoproject.com/en/4.0/topics/security/#cross-site-scripting-xss-protection>`__

We occasionally use the ``safe`` filter within templates and the
``mark_safe`` function in views.

Read the docs on Django’s
`html <https://docs.djangoproject.com/en/4.0/ref/utils/#module-django.utils.html>`__
and
`safestring <https://docs.djangoproject.com/en/4.0/ref/utils/#module-django.utils.safestring>`__
utils.

JavaScript templates
--------------------

HQ uses `Underscore templates <http://underscorejs.org/#template>`__
templates in some areas. Default to using ``<%- ... %>`` syntax to
interpolate values, which properly escapes.

Any value interpolated with ``<%= ... %>`` must be previously escaped.

JavaScript code
---------------

In Knockout, be sure to escape any value passed to an `html
binding <https://knockoutjs.com/documentation/html-binding.html>`__.

The `DOMPurify <https://github.com/cure53/DOMPurify>`__ library is
available to sanitize user input. DOMPurify works by stripping
potentially malicious markup. It does not escape input.
