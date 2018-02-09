# This file is only here so that django will recognize that 
# this is a valid app and run the associated unit tests.
from __future__ import absolute_import
from dimagi.ext.couchdbkit import Document


class _(Document): pass
