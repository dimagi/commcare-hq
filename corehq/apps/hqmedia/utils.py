from corehq.apps.domain.models import LICENSES

MULTIMEDIA_PREFIX = "jr://file/"
IMAGE_MIMETYPES = ["image/jpeg", "image/gif", "image/png"]
AUDIO_MIMETYPES = ["audio/mpeg", "audio/mpeg3", "audio/wav", "audio/x-wav"]
ZIP_MIMETYPES = ["application/zip"]


def most_restrictive(licenses):
    """
    given a list of licenses, this function returns the list of licenses that are as restrictive or more restrictive
    than each of the input licenses
    '<' == less restrictive
    cc < cc-nd, cc-nc, cc-sa
    cc-nd < cc-nc-nd
    cc-nc < cc-nc-sa
    cc-sa < cc-nd, cc-nc-sa
    cc-nc-sa < cc-nc-nd
    """
    licenses = set(licenses)
    for license in licenses:
        if license not in LICENSES:
            raise Exception("Not a valid license type")

    if 'cc-nc-nd' in licenses:
        return ['cc-nc-nd']
    if 'cc-nd' in licenses:
        if 'cc-nc-sa' in licenses or 'cc-nc' in licenses:
            return ['cc-nc-nd']
        else:
            return ['cc-nc-nd', 'cc-nd']
    if 'cc-nc-sa' in licenses or ('cc-sa' in licenses and 'cc-nc' in licenses):
        return ['cc-nc-nd', 'cc-nc-sa']
    if 'cc-nc' in licenses:
        return ['cc-nc-nd', 'cc-nc-sa', 'cc-nc']
    if 'cc-sa' in licenses:
        return ['cc-nc-nd', 'cc-nc-sa', 'cc-nd', 'cc-sa']
    if 'cc' in licenses:
        return ['cc-nc-nd', 'cc-nc-sa', 'cc-nd', 'cc-nc', 'cc-sa', 'cc']
    return ['cc-nc-nd', 'cc-nc-sa', 'cc-nd', 'cc-nc', 'cc-sa', 'cc']
