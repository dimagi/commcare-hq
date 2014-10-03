Analyzing Test Coverage
=======================

This page goes over some basic ways to analyze code coverage locally.

Using coverage.py
-----------------

First thing is to install the coverage.py library::


        $ pip install coverage


Now you can run your tests through the coverage.py program::


        $ coverage run manage.py test commtrack


This will create a binary `commcare-hq/.coverage` file (that is already
ignored by our `.gitignore`) which contains all the magic bits about
what happened during the test run.

You can be as specific or generic as you'd like with what selection of tests
you run through this. This tool will track which lines of code in the app
have been hit during execution of the tests you run. If you're only looking
to analyze (and hopefully increase) coverage in a specific model or utils
file, it might be helpful to cut down on how many tests you're running.


Make an HTML view of the data
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


The simplest (and probably fastest) way to view this data is to build
an HTML view of the code base with the coverage data::


        $ coverage html


This will build a `commcare-hq/coverage-report/` directory with a ton of
HTML files in it. The important one is `commcare-hq/coverage-report/index.html`.


View the result in Vim
^^^^^^^^^^^^^^^^^^^^^^


Install coveragepy.vim (https://github.com/alfredodeza/coveragepy.vim) however
you personally like to install plugins. This plugin is old and out of date
(but seems to be the only reasonable option) so because of this I personally
think the HTML version is better.

Then run `:Coveragepy report` in Vim to build the report (this is kind of slow).

You can then use `:Coveragepy hide` and `:Coveragepy show` to add/remove
the view from your current buffer.
