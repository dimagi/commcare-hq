======
CoreHQ
======
A library for xform processing in django.
-------------------------------------------

Getting Started
----------------

We recommend using virtualenv

Setup virtual env wrapper:
 - easy_install virtualenvwrapper
 - export WORKON_HOME=$HOME/.virtualenvs
 - source /usr/local/bin/virtualenvwrapper.sh
 - mkvirtualenv --no-site-packages <envname>
 - #this will create your env and put you into that env
 - #if you want to switch virtualenvs type workon <virtualenv>


Install dependencies:

pip install -U -r requirements.txt

Other packages needed for download:
 - CouchDB
 - keyczar (http://code.google.com/p/keyczar/)
 - A search engine for haystack (like Solr)
 - memcached for use with johnny_cache
 - postgresql (mysql and sqlite are neither supported nor recommended)
 

Directory Structure
--------------------
corehq
  the main set of apps and code for corehq - should be referenced as corehq.*
lib
  third party code and apps to be in the pythonpath.


