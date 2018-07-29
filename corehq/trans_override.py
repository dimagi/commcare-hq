# coding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
from django.utils.translation import ugettext_noop

messages_to_override = [
    # two_factor/models.py#L47
    ugettext_noop("Token generator"),
]
