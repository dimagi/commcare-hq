Documenting
=============

.. This is a comment

Documentation is awesome.  You should write it.  Here's how.

All the CommCareHQ docs are stored in a ``docs/`` folder in the root of the repo.
To add a new doc, make an appropriately-named rst file in the ``docs/`` directory.
For the doc to appear in the table of contents, add it to the ``toctree`` list in ``index.rst``.

Sooner or later we'll probably want to organize the docs into sub-directories, that's fine, you can link to specific locations like so: ```Installation <intro/install>```.

For a more complete working set of documentation, check out `Django's docs directory <dj_docs_dir_>`_.  This is used to build `docs.djangoproject.com <dj_docs_>`_.

.. _dj_docs_dir: https://github.com/django/django/tree/master/docs
.. _dj_docs: https://docs.djangoproject.com

Index
------

#. :ref:`sphinx` is used to build the documentation.
#. :ref:`doc-style` - Some general tips for writing documentation
#. :ref:`rst` is used for markup.


.. _sphinx:

Sphinx
--------

Sphinx builds the documentation and extends the functionality of rst a bit
for stuff like pointing to other files and modules.

To build a local copy of the docs (useful for testing changes), navigate to the ``docs/`` directory and run ``make html``.
Open ``<path_to_commcare-hq>/docs/_build/html/index.html`` in your browser and you should have access to the docs for your current version (I bookmarked it on my machine).

* `Sphinx Docs <http://sphinx-doc.org/>`_
* `Full index <http://sphinx-doc.org/genindex.html>`_


.. _doc-style:

Writing Documentation
----------------------

For some great references, check out Jacob Kaplan-Moss's series `Writing Great Documentation <jkm_>`_ and this `blog post`_ by Steve Losh.  Here are some takeaways:

* Use short sentences and paragraphs
* Break your documentation into sections to avoid text walls
* Avoid making assumptions about your reader's background knowledge
* Consider `three levels of documentation <jkm_>`_:

   #. Tutorials - quick introduction to the basics
   #. Topical Guides - comprehensive overview of the project; everything but the dirty details
   #. Reference Material - complete reference for the API

.. _jkm: http://jacobian.org/writing/great-documentation/what-to-write/
.. _blog post: http://stevelosh.com/blog/2013/09/teach-dont-tell/


.. _rst:

reStructuredText
-----------------

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



-----------------------

Examples
~~~~~~~~~

Some basic examples adapted from 2 Scoops of Django:

Section Header
^^^^^^^^^^^^^^^

Sections are explained well `here <http://docutils.sourceforge.net/docs/user/rst/quickstart.html#sections>`_ 

.. Basically, use non alphanumeric characters, the first one you use is h1, second is h2,
.. and so on.  It assumes that you're using sections, so Section 1, then 1.1, then 1.1.1,
.. without skipping a level.

**emphasis (bold/strong)**

*italics*

Simple link: http://commcarehq.org

Inline link: `CommCareHQ <https://commcarehq.org>`_

Fancier Link: `CommCareHQ`_

.. _`CommCareHQ`: https://commcarehq.org

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
