from field_audit.auditors import BaseAuditor


class HQAuditor(BaseAuditor):
    """Auditor class for getting HQ information from authenticated requests."""

    def changed_by(self, request):
        if not request:
            # this auditor only knows how to work with requests
            return None
        info = {}
        if request.user.is_authenticated:
            user = request.couch_user
            info["user_type"] = user.doc_type
            info["username"] = user.username
        domain = getattr(request, "domain", None)
        if domain is not None:
            info["domain"] = domain
        return info if info else None
