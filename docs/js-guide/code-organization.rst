Static Files Organization
-------------------------

All JavaScript code should be in a .js file and encapsulated as a
module either using the ES Module syntax or modified-AMD syntax in
legacy code using using ``hqDefine``.

JavaScript files belong in the ``static`` directory of a Django app,
which we structure as follows:

::

   myapp/
     static/myapp/
       css/
       font/
       images/
       js/       <= JavaScript
       scss/
       lib/      <= Third-party code: This should be rare, since most third-party code should be coming from yarn
       spec/     <= JavaScript tests
       ...       <= May contain other directories for data files, i.e., `json/`
     templates/myapp/
       mytemplate.html

To develop with javascript locally, make sure you run ``yarn dev`` and
restart ``yarn dev`` whenever you add a new Webpack Entry Point.

Please review the next section for a more detailed discussion of Static Files
and the use of JavaScript bundlers, like Webpack.
