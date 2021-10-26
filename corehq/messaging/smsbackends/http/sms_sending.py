from corehq.util.urlvalidate.urlvalidate import (
    PossibleSSRFAttempt,
    validate_user_input_url,
)

from corehq.apps.sms.models import SMSBase

from corehq.util.metrics import metrics_counter


def verify_sms_url(url, msg, backend):
    try:
        validate_user_input_url(url)
    except PossibleSSRFAttempt as e:
        metrics_counter('commcare.sms.ssrf_attempt', tags={
            'domain': msg.domain,
            'src': type(backend).__name__,
            'reason': e.reason
        })
        msg.set_system_error(SMSBase.ERROR_FAULTY_GATEWAY_CONFIGURATION)
        raise
