from field_audit.auditors import BaseAuditor


class HQAuditor(BaseAuditor):
    """Auditor class for getting HQ information from authenticated requests."""

    def change_context(self, request):
        if not request:
            # this auditor only knows how to work with requests
            return None
        info = {}
        if request.user.is_authenticated:
            try:
                user = request.couch_user
            except AttributeError:
                # Fetch the couch user manually if it is not set on the request.
                # Only known to happen during registration (sign up).
                from corehq.apps.users.models import CouchUser
                user = CouchUser.get_by_username(request.user.username)
            info["user_type"] = user.doc_type
            info["username"] = user.username
        domain = getattr(request, "domain", None)
        if domain is not None:
            info["domain"] = domain
        return info if info else None
