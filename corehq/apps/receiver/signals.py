from django.dispatch import Signal

post_received = Signal(providing_args=["posted"])
