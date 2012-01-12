from django import forms
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO
import zipfile

class NewXFormForm(forms.Form):
    """Potentially confusing name; HTML Form for creating/uploading a new xform"""
    name = forms.CharField(max_length=50)
    
class NewAppForm(forms.Form):
    name = forms.CharField(max_length=50)

class NewModuleForm(forms.Form):
    name = forms.CharField(max_length=50)

class ModuleConfigForm(forms.Form):
    pass

class ZipUploadForm(forms.Form):

    zip_file = forms.FileField()

    def clean_zipfile(self):
        zip_file = self.clean_zipfile()
        if zip_file.get('content-type') != 'application/zip':
            msg = 'Only .ZIP archive files are allowed.'
            raise forms.ValidationError(msg)
        else:
            # Verify that it's a valid zipfile
            zip = zipfile.ZipFile(StringIO(zip_file['content']))
            bad_file = zip.testzip()
            zip.close()
            del zip
            if bad_file:
                msg = '"%s" in the .ZIP archive is corrupt.' % (bad_file,)
                raise forms.ValidationError(msg)
        return zip_file

    def save(self):
        print "attempting 1"
        zipdata = self.cleaned_data["zip_file"]
        print zipdata
        zip = zipfile.ZipFile(zipdata.temporary_file_path())
        for filename in zip.namelist():
            print filename
        zip.close()