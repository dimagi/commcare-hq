from django.utils.datastructures import SortedDict
from corehq.apps.app_manager.xform import XFormValidationError, XFormError

MULTIMEDIA_PREFIX = "jr://file/"

def get_sorted_multimedia_refs(app):
    images = {}
    audio_files = {}
    has_error = False

    for m in app.get_modules():
        for f in m.get_forms():
            try:
                parsed = f.wrapped_xform()
                if not parsed.exists():
                    continue
                f.validate_form()
                for i in parsed.image_references:
                    if i not in images:
                        images[i] = []
                    images[i].append((m,f))
                for i in parsed.audio_references:
                    if i not in audio_files:
                        audio_files[i] = []
                    audio_files[i].append((m,f))
            except (XFormValidationError, XFormError):
                has_error = True
    sorted_images = SortedDict()
    sorted_audio = SortedDict()
    for k in sorted(images):
        if k:
            sorted_images[k] = images[k]
    for k in sorted(audio_files):
        if k:
            sorted_audio[k] = audio_files[k]
    return sorted_images, sorted_audio, has_error

def get_multimedia_filenames(app):
    images = []
    audio_files = []
    has_error = False
    for m in app.get_modules():
        for f in m.get_forms():
            try:
                parsed = f.wrapped_xform()
                if not parsed.exists():
                    continue
                f.validate_form()
                for i in parsed.image_references:
                    if i and i not in images:
                        images.append(i)
                for a in parsed.audio_references:
                    if a and a not in audio_files:
                        audio_files.append(a)
            except (XFormValidationError, XFormError):
                has_error = True
    return images, audio_files, has_error
