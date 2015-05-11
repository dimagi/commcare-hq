from corehq.apps.app_manager.xform import XFormValidationError, XFormException
from corehq.apps.domain.models import LICENSES

MULTIMEDIA_PREFIX = "jr://file/"
IMAGE_MIMETYPES = ["image/jpeg", "image/gif", "image/png"]
AUDIO_MIMETYPES = ["audio/mpeg", "audio/mpeg3", "audio/wav", "audio/x-wav"]
ZIP_MIMETYPES = ["application/zip"]

def get_application_media(app):
    """
        DEPRECATED.
    """
    from corehq.apps.app_manager.models import Application
    if not isinstance(app, Application):
        raise ValueError("You must pass in an Application object.")

    form_media = {
        'images': set(),
        'audio': set(),
    }
    form_errors = False
    menu_media = {
        'icons': set(),
        'audio': set(),
    }

    def _add_menu_media(item):
        menu_media['icons'].update(set(image.strip() for image in item.all_image_paths() if image))
        menu_media['audio'].update(set(audio.strip() for audio in item.all_audio_paths() if audio))

    for m in app.get_modules():
        _add_menu_media(m)
        for f in m.get_forms():
            _add_menu_media(f)
            try:
                parsed = f.wrapped_xform()
                if not parsed.exists():
                    continue
                f.validate_form()
                for image in parsed.image_references:
                    if image:
                        form_media['images'].add(image.strip())
                for audio in parsed.audio_references:
                    if audio:
                        form_media['audio'].add(audio.strip())
            except (XFormValidationError, XFormException):
                form_errors = True

    return {
        'form_media': form_media,
        'menu_media': menu_media,
    }, form_errors


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
