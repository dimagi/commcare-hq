===========================
Contributing to CommCare HQ
===========================

CommCare HQ is primarily developed by `Dimagi`_, but we welcome contributions.

Code Contributions
------------------
Dimagi tracks many issues internally, but we use github's `issue tracker`_
for public facing issues.  Feel free to browse the issues there and tackle
any you feel equipped to do.  When you update or add comments to an issue
please mention **@dimagi/dimagi-dev** to send an alert to our internal issue
tracking system.  

Please keep in mind that we hold the standard of quality in contributions
to a very high level regardless of source. Contributions which have very
limited scope, come with rigorous tests, and have their purpose outlined
in a Github issue are much more likely to be reviewed for inclusion.

You should ensure the following are true for any PR before it will be 
considered for review or re-review

- The code and architecture comply with `Standards and Best Practices`_
- Any UI components comply with the project `Style Guide`_
- Contributions follow any subsystem specific practices (example: `Javascript Guide`_)
- Automated regression and integration tests are passing
- Any automated feedback (label bot, lint bot, etc) is addressed
- Any previous developer feedback is addressed



When opening a PR, please review our `Guide to Authoring Pull Requests`_.  
You may also be interested in the `Developers category`_ of the `CommCare Forum`_ 
if you have questions or need feedback.

Useful Tools
------------
Here are some tools widely used by CommCareHQ developers

flake8
    Flake8 is run on all PRs automatically. You can run it locally to ensure your
    code meets those standards before opening a PR.

pylint
    It requires some configuration, but this is the most comprehensive python linter
    out there and can provide some useful feedback.

isort
    This will organize the imports in the file you're editing according to the
    ``.isort.cfg`` in the root of the repository.  See how to run this from within
    your editor `here <https://github.com/pycqa/isort/wiki/isort-Plugins>`_

./manage.py show_urls
    Provided by ``django-extensions``, this outputs a list of all URL paths used in the
    project. Pipe the output to ``grep`` to easily find what view handles a particular URL.

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
.. _Standards and Best Practices: STANDARDS.rst
.. _Style Guide: https://www.commcarehq.org/styleguide/
.. _Javascript Guide: docs/js-guide/README.md
.. _Guide to Authoring Pull Requests: https://github.com/dimagi/open-source/blob/master/docs/Writing_PRs.md
.. _Developers category: https://forum.dimagi.com/c/developers
.. _CommCare Forum: https://forum.dimagi.com/
.. _Read the Docs: https://commcare-hq.readthedocs.io/
.. _reStructuredText: https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html
.. _autoclass: https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html


Updating requirements
---------------------
To update requirements edit:

* ``requirements/requirements.in`` for packages for all environments

* ``requirements/prod-requirements.in`` for packages for production environments only

* ``requirements/test-requirements.in`` for packages for test environment only

* ``requirements/dev-requirements.in`` for packages for dev environment only

and run ``make requirements``.

To upgrade all requirements to their latest allowed version you can run
``make upgrade-requirements``—this usually results in a large number of upgrades
and is not something we can merge easily, but it is sometimes a useful exploratory first step.

PR labels
---------

Product labels
~~~~~~~~~~~~~~
All PRs must be tagged with one of the following PR labels. For PRs from external
contributors the onus is on the reviewer to add the labels.

- product/all-users-all-environments
- product/prod-india-all-users
- product/custom
- product/feature-flag
- product/invisible
- product/admin

Label descriptions can be seen on the GitHub `labels`_ page or in the
`.github/labels.yml`_ configuration file.

.. _labels: https://github.com/dimagi/commcare-hq/labels
.. _.github/labels.yml: .github/labels.yml

Reindex / migration
~~~~~~~~~~~~~~~~~~~
Any PR that will require a database migration or some kind of data reindexing to be done
must be labeled with the **reindex/migration** label. This label will get automatically applied
if the PR changes `certain files`_ but it can also be added manually.

It is necessary to add a `RequestReindex`_ Django migration operation, which may
also require adding a new migration file, if the **reindex/migration** label is added to a PR on
account of Couch ``_design`` doc changes (or if a new Elasticsearch index is added, but this
will soon change). The following command will automatically add a migration and update the
Couch views lock file when a reindex is required on account of Couch view changes::

    $ ./manage.py makemigrations preindex

A change log entry should be published in `commcare-cloud`_ to alert
operators to run the migration before deploying if it may disrupt the normal deploy cycle (if it
will run for a long time on any environment, for example).

Any PR with this label will fail the `required-labels` check. This is intentional to prevent
premature merging of the PR.

.. _certain files: .github/labels.yml#L12-L13
.. _RequestReindex: corehq/preindex/django_migrations.py
.. _commcare-cloud: https://github.com/dimagi/commcare-cloud/

Risk
~~~~
PRs that touch certain files will be automatically flagged with a "Risk" label,
either medium or high. This includes heavily-used workflows where a bug would have a high impact
and also areas that are technically complex, difficult to roll back, etc.
These PRs will receive extra scrutiny and should have especially solid test coverage and/or
manual testing. Alternatively, the PR description may explain why the PR is not genuinely high risk.

QA / Work in progress
~~~~~~~~~~~~~~~~~~~~~~
PRs that are not ready to be merged can be labeled with one of the following labels:

- awaiting QA
- Open for review: do not merge

As long as either of these labels are present on the PR it will have a pending status.
