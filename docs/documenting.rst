Documenting
===========

.. This is a comment

Documentation is awesome.  You should write it.  Here's how.

All the CommCare HQ docs are stored in a ``docs/`` folder in the root of the repo.
To add a new doc, make an appropriately-named rst file in the ``docs/`` directory.
For the doc to appear in the table of contents, add it to the ``toctree`` list in ``index.rst``.

Sooner or later we'll probably want to organize the docs into sub-directories,
that's fine, you can link to specific locations like so: ``Installation
<intro/install>``.

For a nice example set of documentation, check out `Django's docs directory
<dj_docs_dir_>`_. This is used to build `docs.djangoproject.com <dj_docs_>`_.

.. _dj_docs_dir: https://github.com/django/django/tree/master/docs
.. _dj_docs: https://docs.djangoproject.com

Index
-----

#. :ref:`sphinx` is used to build the documentation.
#. :ref:`readthedocs` is used for hosting.
#. :ref:`doc-style` - Some general tips for writing documentation
#. :ref:`rst` is used for markup.
#. :ref:`editors` with RestructuredText support


.. _sphinx:

Sphinx
------

Sphinx builds the documentation and extends the functionality of rst a bit
for stuff like pointing to other files and modules.

To build a local copy of the docs (useful for testing changes), navigate to the
``docs/`` directory and run ``make html``. Open
``<path_to_commcare-hq>/docs/_build/html/index.html`` in your browser and you
should have access to the docs for your current version (I bookmarked it on my
machine).

* `Sphinx Docs <http://sphinx-doc.org/>`_
* `Full index <http://sphinx-doc.org/genindex.html>`_

.. _readthedocs:

Read the Docs
-------------

Dimagi maintains the hosted version of the documentation at readthedocs.io. For
Dimagi employees, the credentials are maintained in our internal password manager under the "readthedocs" entry.

The configuration for *Read the Docs* lives in ``.readthedocs.yml``, which calls the
``docs/conf.py`` script.

Due to problematic dependencies that need to be mocked, we cannot properly setup django apps until after
``docs/conf.py`` has been applied. We then must be aware that we are performing a docs build, at which point we can run
`django.setup()` in ``corehq/__init__.py``. We use an environment variable (`DOCS_BUILD`) to convey this information,
which is set in the Admin UI of our readthedocs.io account.

Troubleshooting
~~~~~~~~~~~~~~~

The docs are built with every new merge to master. This build can fail
completely, or "succeed" with errors. If you made a change that's not appearing,
or if ``autodoc`` doesn't seem to be working properly, you should check the build.

On *Read the Docs*, in the bottom left, you should see "v: latest". Click to expand,
then click "Builds". There you should see a build history (you don't need to log
in for this). Click on the latest build. I find the "view raw" display to be
more useful.  That should show logs and any tracebacks.

Running ``autodoc`` or ``automodule`` requires that sphinx be able to load the
code to import docstrings. This means that ~all of the source code's
requirements to be installed, and the code cannot do complex stuff like database
queries on module load.  Build failures are likely caused by issues there.

Replicating the build environment
.................................

*Read the Docs* builds in an environment that doesn't have any support services,
so turn those off. Next, make a new virtual environment with just the docs
requirements. Finally, build the docs, which should surface any errors that'd
appear on the build server.

.. code-block:: sh

   $ cd commcare-hq/
   $ mkvirtualenv --python=python3.9 hq-docs
   $ pip install -r requirements/docs-requirements.txt
   $ cd docs/
   $ make html

.. _doc-style:

Writing Documentation
---------------------

For some great references, check out Jacob Kaplan-Moss's series `Writing Great Documentation <jkm_>`_ and this
`blog post`_ by Steve Losh.  Here are some takeaways:

* Use short sentences and paragraphs
* Break your documentation into sections to avoid text walls
* Avoid making assumptions about your reader's background knowledge
* Consider `three types of documentation <jkm_wtw_>`_:

   #. Tutorials - quick introduction to the basics
   #. Topical Guides - comprehensive overview of the project; everything but the dirty details
   #. Reference Material - complete reference for the API

One aspect that Kaplan-Moss doesn't mention explicitly (other than advising us to "Omit fluff" in his
`Technical style <jkm_ts_>`_ piece) but is clear from both his documentation series and the Django documentation,
is *what not to write*.
It's an important aspect of the readability of any written work, but has other implications when it comes to
technical writing.

Antoine de Saint Exupéry wrote, "... perfection is attained not when there is nothing more to add, but when there
is nothing more to remove."

Keep things short and take stuff out where possible.
It can help to get your point across, but, maybe more importantly with documentation, means there is less that
needs to change when the codebase changes.

Think of it as an extension of the DRY principle.


.. _jkm: http://jacobian.org/writing/great-documentation/
.. _blog post: http://stevelosh.com/blog/2013/09/teach-dont-tell/
.. _jkm_wtw: http://jacobian.org/writing/what-to-write/
.. _jkm_ts: http://jacobian.org/writing/technical-style/


.. _rst:

reStructuredText
----------------

reStructuredText is a markup language that is commonly used for Python documentation.  You can view the source of this document or any other to get an idea of how to do stuff (this document has hidden comments).  Here are some useful links for more detail:

* `rst quickreference <http://docutils.sourceforge.net/docs/user/rst/quickref.html>`_
* `Sphinx guide to rst <http://sphinx-doc.org/rest.html>`_
* `reStructuredText full docs <http://docutils.sourceforge.net/rst.html>`_
* `Referencing arbitrary locations and other documents <http://sphinx-doc.org/markup/inline.html#ref-role>`_


.. This is a normal comment

.. 
    This is a block comment, none of this will appear in the generated HTML.

    RST has basic inline markup just like Markdown, but a lot of its flexibility and extensibility come in this form:  A line beginning with two periods and a space indicates that this line is explicitly markup.

    This hyperlink target can be referred to elsewhere
    .. _my-hyperlink-target: http://www.commcarehq.org/
    .. _my-section-reference:
    These targets can also refer to sections of the document (ctrl+f for _rst)

    A similar syntax is used for code blocks:

    .. code-block:: python

        def myfn(m, n):
            return m + n

    You can also just start a code block like this::

        def myfn(m, n):
            return m + n

    Of course, none of this will show up in the html, because it's all part of the comment block (by indentation)


.. _editors:

Editors
-------

While you can use any text editor for editing RestructuredText
documents, I find two particularly useful:

* PyCharm (or other JetBrains IDE, like IntelliJ), which has great
  syntax highlighting and linting.
* Sublime Text, which has a useful plugin for hard-wrapping lines called
  `Sublime Wrap Plus`_. Hard-wrapped lines make documentation easy to
  read in a console, or editor that doesn't soft-wrap lines (i.e. most
  code editors).
* Vim has a command ``gq`` to reflow a block of text (``:help gq``). It
  uses the value of ``textwidth`` to wrap (``:setl tw=75``).  Also check
  out ``:help autoformat``.  Syntastic has a rst linter.  To make a line a
  header, just ``yypVr=`` (or whatever symbol you want).


.. _Sublime Wrap Plus: https://github.com/ehuss/Sublime-Wrap-Plus

-----------------------

Examples
~~~~~~~~

Some basic examples adapted from 2 Scoops of Django:

Section Header
..............

Sections are explained well `here <http://docutils.sourceforge.net/docs/user/rst/quickstart.html#sections>`_ 

.. Basically, use non alphanumeric characters, the first one you use is h1, second is h2,
.. and so on.  It assumes that you're using sections, so Section 1, then 1.1, then 1.1.1,
.. without skipping a level.

**emphasis (bold/strong)**

*italics*

Simple link: http://commcarehq.org

Inline link: `CommCare HQ <https://commcarehq.org>`_

Fancier Link: `CommCare HQ`_

.. _`CommCare HQ`: https://commcarehq.org

#. An enumerated list item
#. Second item

* First bullet
* Second bullet
    * Indented Bullet
    * Note carriage return and indents

Literal code block::

    def like():
        print("I like Ice Cream")

    for i in range(10):
        like()

Python colored code block (requires pygments):

.. code-block:: python

    # You need to "pip install pygments" to make this work.

    for i in range(10):
        like()

JavaScript colored code block:

.. code-block:: javascript

    console.log("Don't use alert()");
