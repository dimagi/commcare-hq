from corehq.apps.domain.auth import formplayer_auth
from corehq.apps.ota.case_restore import get_case_restore_response


@formplayer_auth
def migration_restore(request, domain, case_id):
    """Moved to `ota` app. Can be removed once Formplayer is updated."""
    return get_case_restore_response(domain, case_id)
