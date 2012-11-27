from django import forms
from django.core.urlresolvers import reverse
from django.forms.util import ErrorList
import magic
from corehq.apps.hqmedia import utils
from corehq.apps.hqmedia.models import CommCareMultimedia, CommCareImage, CommCareAudio
import zipfile

class HQMediaZipUploadForm(forms.Form):

    zip_file = forms.FileField(required=True, label="ZIP file with CommCare multimedia:")
    repopulate_multimedia_map = forms.BooleanField(required=False,
                                label="Remove all previous references to multimedia files in my application.")
    replace_existing_media = forms.BooleanField(required=False,
                                label="Replace any existing multimedia files with this file.")

    def clean_zip_file(self):
        if 'zip_file' in self.cleaned_data:
            zip_file = self.cleaned_data['zip_file']
            mime = magic.Magic(mime=True)
            data = zip_file.file.read()
            content_type = mime.from_buffer(data)
            if content_type != 'application/zip':
                raise forms.ValidationError('Only .ZIP archive files are allowed.')
            else:
                # Verify that it's a valid zipfile
                zip_file.file.seek(0)
                zip = zipfile.ZipFile(zip_file)
                bad_file = zip.testzip()
                if bad_file:
                    msg = '"%s" in the .ZIP archive is corrupt.' % (bad_file,)
                    raise forms.ValidationError(msg)
                return zip

    def save(self, domain, app, username, cache_handler=None):
        orig_images, orig_audio, _ = utils.get_multimedia_filenames(app)
        form_images = [i.replace(utils.MULTIMEDIA_PREFIX, '').lower().strip() for i in orig_images]
        form_audio = [a.replace(utils.MULTIMEDIA_PREFIX, '').lower().strip() for a in orig_audio]

        if self.cleaned_data["repopulate_multimedia_map"]:
            app.multimedia_map = {}
            app.save()
        replace_attachment = self.cleaned_data["replace_existing_media"]

        zip = self.cleaned_data["zip_file"]
        num_files = len(zip.namelist())
        if cache_handler:
            cache_handler.sync()
            cache_handler.data["processed_length"] = num_files
            cache_handler.save()
        
        unknown_files = []
        for index, path in enumerate(zip.namelist()):
            path = path.strip()
            path_lower = path.lower()
            if path_lower.endswith("/") or path_lower.endswith("\\") or \
                path_lower.endswith(".ds_store"):
                continue

            media = None
            form_path = None
            data = None
            if path_lower in form_images:
                form_path = orig_images[form_images.index(path_lower)]
                data = zip.read(path)
                media = CommCareImage.get_by_data(data)
            elif path_lower in form_audio:
                form_path = orig_audio[form_audio.index(path_lower)]
                data = zip.read(path)
                media = CommCareAudio.get_by_data(data)
            else:
                unknown_files.append(path)

            if media:
                media.attach_data(data,
                     upload_path=path,
                     username=username,
                     replace_attachment=replace_attachment)
                media.add_domain(domain, owner=True)
                app.create_mapping(media, form_path)
            if cache_handler:
                cache_handler.sync()
                cache_handler.data["processed"] = index+1
                cache_handler.save()
        zip.close()
        return {"successful": unknown_files}

class HQMediaFileUploadForm(forms.Form):

    multimedia_class = forms.CharField(initial="CommCareMultimedia", widget=forms.HiddenInput)
    media_file = forms.FileField(required=True, label="Please select a file to reference:")
    multimedia_form_path = forms.CharField(required=True, widget=forms.HiddenInput)
    multimedia_upload_action = forms.BooleanField(required=False, widget=forms.HiddenInput)
    old_reference = forms.CharField(widget=forms.HiddenInput)

    def clean_media_file(self):
        if 'media_file' in self.cleaned_data:
            media_file = self.cleaned_data['media_file']
            mime = magic.Magic(mime=True)
            data = media_file.file.read()
            content_type = mime.from_buffer(data)
            if content_type == 'application/zip':
                raise forms.ValidationError('Please use the zip file uploader to upload zip files.')
            media = CommCareMultimedia.get_doc_class(self.cleaned_data['multimedia_class'])
            if not media.validate_content_type(content_type):
                raise forms.ValidationError('That was not a valid file type, please try again with a different file.')
            return media_file


    def save(self, domain, app, username, cache_handler):
        media_class = CommCareMultimedia.get_doc_class(self.cleaned_data['multimedia_class'])
        media_file = self.cleaned_data['media_file']
        replace_attachment = self.cleaned_data['multimedia_upload_action']
        form_path = self.cleaned_data['multimedia_form_path']

        media_file.file.seek(0)
        data = media_file.file.read()
        media = media_class.get_by_data(data)
        if cache_handler:
            cache_handler.sync()
            cache_handler.data["processed_length"] = 1
            cache_handler.save()
        if media:
            media.attach_data(data,
                     upload_path=media_file.name,
                     username=username,
                     replace_attachment=replace_attachment)
            media.add_domain(domain, owner=True)
            app.create_mapping(media, form_path)
        if cache_handler:
            cache_handler.sync()
            cache_handler.data["processed"] = 1
            cache_handler.save()
        old_ref = self.cleaned_data['old_reference']
        new_ref = reverse("hqmedia_download", args=[domain,
                                                media.doc_type,
                                                media._id])
        return {"successful" : {old_ref: new_ref}}
        