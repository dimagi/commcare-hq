from couchdbkit import DocumentSchema, BooleanProperty, StringProperty, ResourceNotFound
from corehq.apps.domain.models import Domain


class AuthContext(DocumentSchema):
    authenticated = BooleanProperty(default=False)
    domain = StringProperty()
    user_id = StringProperty()

    def auth_required(self):
        domain = Domain.get_by_name(self.domain, strict=True)
        if domain:
            return domain.secure_submissions
        else:
            raise ResourceNotFound('No domain with name %s' % self.domain)

    def is_valid(self):
        return self.authenticated or not self.auth_required()
