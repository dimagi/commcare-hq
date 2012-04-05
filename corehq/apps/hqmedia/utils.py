from django.core.urlresolvers import reverse
from django.utils.datastructures import SortedDict
import os
from corehq.apps.app_manager.xform import XFormValidationError, XFormError
from corehq.apps.hqmedia.models import CommCareMultimedia, CommCareAudio, CommCareImage

MULTIMEDIA_PREFIX = "jr://file/"
IMAGE_MIMETYPES = ["image/jpeg", "image/gif", "image/png"]
AUDIO_MIMETYPES = ["audio/mpeg", "audio/mpeg3"]
ZIP_MIMETYPES = ["application/zip"]

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

class HQMediaMatcher():

    def __init__(self, app, domain, username):
        self.image_paths, self.audio_paths, _ = get_multimedia_filenames(app)
        self.images = [os.path.basename(i.replace(MULTIMEDIA_PREFIX+'commcare/media/', '').lower().strip()) for i in self.image_paths]
        self.audio = [os.path.basename(a.replace(MULTIMEDIA_PREFIX+'commcare/audio/', '').lower().strip()) for a in self.audio_paths]

        self.app = app
        self.domain = domain
        self.username = username

    def clear_map(self):
        self.app.multimedia_map = {}
        self.app.save()

    def match_zipped(self, zip, replace_existing_media=True):
        unknown_files = []
        matched_audio = []
        matched_images = []

        for index, path in enumerate(zip.namelist()):
            path = path.strip()
            filename = os.path.basename(path.lower())

            if not filename:
                continue

            media = None
            form_path = None
            data = None

            if filename in self.images:
                form_path = self.image_paths[self.images.index(filename)]
                data = zip.read(path)
                media = CommCareImage.get_by_data(data)
                matched_images.append({"upload_path": path,
                                       "app_path": form_path,
                                       "url": reverse("hqmedia_download", args=[media.doc_type, media._id]) })
            elif filename in self.audio:
                form_path = self.audio_paths[self.audio.index(filename)]
                data = zip.read(path)
                media = CommCareAudio.get_by_data(data)
                matched_audio.append({"upload_path": path,
                                       "app_path": form_path,
                                       "url": reverse("hqmedia_download", args=[media.doc_type, media._id]) })
            else:
                unknown_files.append(path)

            if media:
                media.attach_data(data,
                    upload_path=path,
                    username=self.username,
                    replace_attachment=replace_existing_media)
                media.add_domain(self.domain)
                self.app.create_mapping(media, form_path)

        zip.close()
        return matched_images, matched_audio, unknown_files

    def match_file(self, uploaded_file, replace_existing_media=True):
        try:
            filename = uploaded_file.name

            if filename in self.images:
                form_path = self.image_paths[self.images.index(filename)]
                data = uploaded_file.file.read()
                media = CommCareImage.get_by_data(data)
            elif filename in self.audio:
                form_path = self.audio_paths[self.audio.index(filename)]
                data = uploaded_file.file.read()
                media = CommCareAudio.get_by_data(data)
            else:
                uploaded_file.close()
                return False, {}

            media.attach_data(data,
                upload_path=filename,
                username=self.username,
                replace_attachment=replace_existing_media)
            media.add_domain(self.domain)
            self.app.create_mapping(media, form_path)

            return True, {"upload_path": filename,
                          "app_path": form_path,
                          "url": reverse("hqmedia_download", args=[media.doc_type, media._id])}

        except Exception as e:
            print e

        return False, {}



