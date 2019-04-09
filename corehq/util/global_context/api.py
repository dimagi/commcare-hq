from __future__ import absolute_import
from __future__ import unicode_literals
import threading


class GlobalContex(threading.local):
    request = None

    # used for passing username when outside of a request
    current_domain = None

    # used for passing username when outside of a request
    current_username = None

    # This is the view name or management command name
    # (not all management commands set this)
    context_key = None

    def reset(self):
        self.request = None
        self.current_domain = None
        self.current_username = None
        self.context_key = None

    def get_current_domain(self):
        return self.current_domain or getattr(self.request, 'domain', None)

    def get_current_username(self):
        if self.current_username:
            return self.current_username

        user = getattr(self.request, 'user', None)
        if user:
            return user.username


global_context = GlobalContex()
