Static Files Organization
-------------------------

All\* JavaScript code should be in a .js file and encapsulated as a
module using ``hqDefine``.

JavaScript files belong in the ``static`` directory of a Django app,
which we structure as follows:

::

   myapp/
     static/myapp/
       css/
       font/
       images/
       js/       <= JavaScript
       less/
       lib/      <= Third-party code: This should be rare, since most third-party code should be coming from yarn
       spec/     <= JavaScript tests
       ...       <= May contain other directories for data files, i.e., `json/`
     templates/myapp/
       mytemplate.html

\* There are a few places we do intentionally use script blocks, such as
configuring less.js in CommCare HQ’s main template,
``hqwebapp/base.html``. These are places where there are just a few
lines of code that are truly independent of the rest of the site’s
JavaScript. They are rare.
