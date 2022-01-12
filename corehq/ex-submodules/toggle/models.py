# Import to avoid pickling errors due to caching of Toggle.get_cached that happened before the class moved.
# This can be removed 24 hours after its deploy.
# Practically, that means at least 6 weeks after merge, to allow self-hosting environments to update.
from corehq.apps.toggle_ui.models import Toggle   # noqa
