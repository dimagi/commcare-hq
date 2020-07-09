==========================
Contributing to CommCareHQ
==========================

CommCareHQ is primarily developed by `Dimagi`_, but we welcome contributions.

Code Contributions
------------------
Dimagi tracks most issues internally, but we use github's `issue tracker`_
for public facing issues.  Feel free to browse the issues there and tackle
any you feel equipped to do.  When you update or add comments to an issue
please mention **@dimagiupdate** to send an alert to our internal issue
tracking system.  

Please keep in mind that we hold the standard of quality in contributions
to a very high level regardless of source. Contributions which have very
limited scope, come with rigorous tests, and have their purpose outlined
in a Github issue are much more likely to be reviewed for inclusion.

Before submitting a PR, review our `Guide to Authoring Pull Requests`_.  
You may also be interested in the `Developers category`_ of the `CommCare Forum`_ 
if you have questions or need feedback.

CommCare Enhancement Proposals
------------------------------
For larger changes or new features we encourage the use of the `CommCare Enhancement Proposal`_
process which gives the team a chance to give feedback on ideas before the code work begins.

.. _CommCare Enhancement Proposal: https://commcare-hq.readthedocs.io/cep.html

Bug Reports
-----------
To file a bug report, please follow the system outlined in our `bug
reports`_ wiki page.  You are also welcome to submit an accompanying pull
request if you are able to resolve the issue.

Documentation Contributions
---------------------------
CommCare HQ's technical documentation is available at `Read the Docs`_.
It is written in reStructuredText_.

When documenting features, it is good practice to keep the documentation
close to its code, so that it can easily be found. A good example of
this is the documentation for User Configurable Reporting. The code is
situated in the *corehq/apps/userreports/* directory, and its documentation
is in *corehq/apps/userreports/README.rst*. In general,
*corehq/apps/[myapp]/README.rst* is typically a good starting point for
documentation.

The User Configurable Reporting documentation also shows another good
practice; it uses reStructuredText's autoclass_ directive to include the
documentation written as docstrings in the codebase. This avoids
duplication, and means that when the codebase is changed, the documentation
is updated automatically with it.

Add a file to the *docs/* directory, and a reference to it in
*docs/index.rst* under the ``toctree`` directive, to include it with the
rest of CommCare HQ's documentation. Again, you can refer to *docs/ucr.rst*
to see how that works.


.. _Dimagi: http://www.dimagi.com/
.. _issue tracker: https://github.com/dimagi/commcare-hq/issues
.. _bug reports: https://confluence.dimagi.com/display/commcarepublic/Bug+Reports
.. _Guide to Authoring Pull Requests: https://github.com/dimagi/code-review/blob/master/Writing_PRs.md
.. _Developers category: https://forum.dimagi.com/c/developers
.. _CommCare Forum: https://forum.dimagi.com/
.. _Read the Docs: https://commcare-hq.readthedocs.io/
.. _reStructuredText: https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html
.. _autoclass: https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html


Updating requirements
---------------------
To update requirements edit
``requirements/requirements.in`` for packages for all environments
``requirements/prod-requirements.in`` for packages for production environments only
``requirements/test-requirements.in`` for packages for test environment only
``requirements/dev-requirements.in`` for packages for dev environment only

and run ``make requirements``.

To upgrade all requirements to their latest allowed version you can run
``make upgrade-requirements``—this usually results in a large number of upgrades
and is not something we can merge easily, but it is sometimes a useful exploratory first step.
