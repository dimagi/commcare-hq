from __future__ import absolute_import
from __future__ import unicode_literals
from django.dispatch import Signal

commcare_domain_post_save = Signal(providing_args=["domain"])
commcare_domain_pre_delete = Signal(providing_args=["domain"])
