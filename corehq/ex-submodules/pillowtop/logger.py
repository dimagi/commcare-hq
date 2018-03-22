from __future__ import absolute_import
from __future__ import unicode_literals
import logging


pillow_logging = logging.getLogger("pillowtop")
pillow_logging.setLevel(logging.INFO)  # todo: this should be done explicitly in settings
