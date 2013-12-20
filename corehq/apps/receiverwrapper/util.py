import re
from corehq.apps.receiverwrapper.auth import AuthContext
import receiver


def get_submit_url(domain, app_id=None):
    if app_id:
        return "/a/{domain}/receiver/{app_id}/".format(domain=domain, app_id=app_id)
    else:
        return "/a/{domain}/receiver/".format(domain=domain)


def submit_form_locally(instance, domain, app_id=None, user_id=None,
                        authenticated=False):
    response = receiver.SubmissionPost(
        app_id=app_id,
        domain=domain,
        instance=instance,
        attachments={},
        auth_context=AuthContext(
            domain=domain,
            user_id=user_id,
            authenticated=authenticated,
        )
    ).get_response()
    return response


def get_meta_appversion_text(xform):
    form_data = xform.form
    try:
        text = form_data['meta']['appVersion']['#text']
    except KeyError:
        return None

    # just make sure this is a longish string and not something like '2.0'
    if isinstance(text, (str, unicode)) and len(text) > 5:
        return text
    else:
        return None


def get_build_version(xform):
    """
    there are a bunch of unreliable places to look for a build version
    this abstracts that out

    """
    patterns = [
        r' #(\d+) ',
        'b\[(\d+)\]',
    ]

    appversion_text = get_meta_appversion_text(xform)
    if appversion_text:
        for pattern in patterns:
            match = re.search(pattern, appversion_text)
            if match:
                build_number, = match.groups()
                return int(build_number)

    xform_version = xform.version
    if xform_version and xform_version != '1':
        return int(xform_version)
