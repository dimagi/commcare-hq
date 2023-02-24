Code Review
===========

All of the general standards of code review apply equally to JavaScript.
See `Code Contributions and Review <https://github.com/dimagi/open-source/blob/master/docs/code_review.md>`__
for general guidance on code review. This document summarizes points to keep
in mind specifically when reviewing JavaScript in CommCare HQ.


Language
--------

Make any user-facing language as clear as possible.

- Proofread it.
- Limit jargon and overly technical language (using pre-existing HQ terms is okay)
- Don't let internal names bleed into user-facing content

   - "Lookup tables" not "fixtures"
   - "Web apps" not "cloudcare"
   - "Mobile worker" not "mobile user" or "CommCare User"
   - etc.

Translations
------------

- All user-facing text should be translated with ``gettext``, which is globally available in HQ JavaScript.
- Strings that contain variables should use ``_.template`` as described in the
  `translations docs <https://commcare-hq.readthedocs.io/translations.html#tagging-strings-in-javascript>`__.

Time Zones
----------

- All user-facing dates and times should be displayed in a time zone that will make sense for the user. Look at
  usage of ``UserTime`` and more generally at ``corehq.util.timezones``.

Security
--------

- Use ``<%- ... %>`` in Underscore templates to HTML escape values.
- Use ``DomPurify`` to HTML escape user input that will be displayed, but not in a template.

Delays and Errors
-----------------

- Any potentially long-running requests, including all AJAX requests, should use a spinner or similar indicator.

   - jQuery: Use ``disableButton`` to disable & add a spinner, then ``enableButton`` when the request succeeds or fails.
   - Knockout: These usally need custom-but-usually-short disable/spinner code, probably using a boolean observable
     and a ``disable`` binding in the HTML.
   - There may not be spinner/disable code if there's an HTML form and it uses the ``disable-on-submit`` class.

- Any AJAX requests should have an ``error`` callback.

   - This usually doesn't need to be fancy, just to display a generic "Try again"-type error near the action that
     was taken. Most requests aren't error-prone, this is typically just to defend against generic platform
     errors like the user getting logged out.

Coding Standards
----------------

Again, standards in JavaScript are largely the same as in Python. However, there are a few issues that are either
specific to JavaScript or more frequently arise in it:

- Naming. JavaScript is often messy because it sometimes uses server naming conventions, which are different, for server
  data. Push the author to leave the code better than they found it. Don't allow the same identifier to be used
  with different capitalizations, e.g., ``firstName`` and ``first_name`` in the same file. Find a synonym for one
  of them.
- JavaScript should be enclosed in modules and those modules should explicitly declare dependencies, as in the
  first code block `here
  <https://commcare-hq.readthedocs.io/js-guide/dependencies.html#how-do-i-know-whether-or-not-im-working-with-requirejs>`__. Exceptions are app manager, reports, and web apps.
- Avoid long lists of params. Prefer kwargs-style objects and use ``assert_properties`` to verify they contain the
  expected options.
- Make sure any js access of `initial page data <https://commcare-hq.readthedocs.io/js-guide/integration-patterns.html#javascript-in-django-templates>`__ is guaranteed not to happen until the page is fully loaded.
  Not doing so risks a
  race condition that will break the page. Keep an eye out that any new initial page data accessed in js is made
  available in HTML (usually not an issue unless the author didn't test at all).
- Prefer knockout to jQuery. Avoid mixing knockout and jQuery.  Recall that you don't have to solve the author's
  problems. It's enough to say, "This is a lot of jQuery, have you considered making a knockout model?"
