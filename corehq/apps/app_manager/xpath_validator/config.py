from __future__ import absolute_import
from __future__ import unicode_literals
import os


def get_xpath_validator_path():
    return os.path.join(
        os.path.abspath(os.path.dirname(__file__)), "nodejs", "xpathValidator.js")
