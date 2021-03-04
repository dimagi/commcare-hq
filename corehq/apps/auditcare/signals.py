from django.dispatch import Signal

user_login_failed = Signal(providing_args=['request', 'username'])
