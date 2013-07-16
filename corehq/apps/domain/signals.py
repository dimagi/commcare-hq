from django.dispatch import Signal

commcare_domain_post_save = Signal(providing_args=["domain"])