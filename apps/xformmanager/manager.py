from __future__ import absolute_import

import uuid
import subprocess
import copy
from subprocess import PIPE

from django.db.models import ForeignKey

from xformmanager.storageutility import * 
from xformmanager.xformdef import FormDef
from xformmanager.copy import collect_related, copy_related
from xformmanager.models import MetaDataValidationError, Metadata
from receiver.models import Attachment

class XFormManager(object):
    """A central location for managing xforms.  This object includes 
       functionality to upload, insert into, and delete XForms.  The forms
       are translated into database tables where submission data is flattened
       out and saved for easy reporting access.

       This class makes the process of handling formdefs (our representation 
       of xform schemas) and formdefmodels (db interaction layer), completely 
       transparent to the programmers.
    """
    
    def __init__(self):
        self.su  = StorageUtility()

    def remove_schema(self, id, remove_submissions=False):
        """Remove a schema entirely, dropping its database tables and optionally
           deleting all submission to it as well.""" 
        self.su.remove_schema(id, remove_submissions)    

    def remove_data(self, formdef_id, id, remove_submission=False):
        """Deletes a single row of data from the table, optionally 
           deleting the original submission to it as well.""" 
        self.su.remove_instance_matching_schema(formdef_id, id, remove_submission)
        
    def save_schema_POST_to_file(self, stream, file_name):
        """Given a form post (instance) saves that form to disk, without
           doing any additional processing."""
        try:
            type = file_name.rsplit('.',1)[1]
        except IndexError:
            # POSTed file has no extension
            type = "xform"
        filename_on_disk = self._save_schema_stream_to_file(stream, type)
        return filename_on_disk

    def save_form_data(self, attachment):
        """Given an attachment attempt to match it to a known (registered)
           XForm and parse out its data, saving to the flattened tables and
           creating metadata for it.
           
           Returns True on success and False on failure"""
        return self.su.save_form_data(attachment)
    
    def validate_schema(self, file_name):
        """validate schema 
           Returns a tuple (is_valid, error)
           is_valid - True if valid, False if not
           error - Relevant validation error
        """
        fout = open(file_name, 'r')
        formdef = FormDef(fout)
        fout.close()
        try:
            formdef.validate()
        except FormDef.FormDefError, e:
            return False, e
        except MetaDataValidationError, e:
            return False, e
        # other failures should propagate up the stack.
        return True, None

    def create_schema_from_file(self, new_file_name, domain=None):
        """Given a xsd schema, create the django models and database
           tables reqiured to submit data to that form."""
        # process xsd file to FormDef object
        fout = open(new_file_name, 'r')
        formdef = FormDef(fout, domain=domain)
        fout.close()
        formdefmodel = self.su.add_schema(formdef)
        formdefmodel.xsd_file_location = new_file_name
        formdefmodel.save()
        return formdefmodel

    def add_schema_manually(self, schema, type, domain=None):
        """Manually register a schema."""
        file_name = self._save_schema_string_to_file(schema, type)
        return self.create_schema_from_file(file_name, domain)

    def add_schema(self, file_name, input_stream, domain=None):
        """ we keep this api open for the unit tests """
        file_name = self.save_schema_POST_to_file(input_stream, file_name)
        return self.create_schema_from_file(file_name, domain)
    
    
    def repost_schema(self, form):
        """Repost a schema entirely, dropping its database tables and then
           recreating them and reposting all submissions that had previously
           matched.  Useful during upgrades.""" 
        
        # copy the original form to map properties
        form_model_copy = copy.copy(form)
                
        # get related objects so we can migrate them
        related_objs = collect_related(form)
        copies = copy_related(related_objs)
        
        # store the attachments that mapped to the form for later reposting
        matching_meta_attachments = list(Metadata.objects.filter(formdefmodel=form)\
                                         .values_list('attachment__id', flat=True))
        
        # copy the form's XSD/XForm to a temporary location for reposting  
        xsd_file = form.xsd_file_location
        temp_xsd_path = os.path.join(tempfile.gettempdir(), "form%s.xsd" % form.id)
        shutil.copy(xsd_file, temp_xsd_path)
        if form.xform_file_location:
            xform_file = form.xform_file_location
            temp_xform_path = os.path.join(tempfile.gettempdir(), "form%s.xml" % form.id)
            shutil.copy(xform_file, temp_xform_path)
        
        # drop
        self.remove_schema(form.id, remove_submissions=False)
        
        # add
        file_to_post = temp_xform_path if form.xform_file_location else temp_xsd_path
        type = "xform" if form.xform_file_location else "xsd"
        file_stream = open(file_to_post, "r")
        fileback = self._save_schema_stream_to_file(file_stream, type)
        new_form = self.create_schema_from_file(fileback, form_model_copy.domain)
        
        # migrate properties
        for property in ["submit_time", "submit_ip", "bytes_received", "form_display_name", 
                         "date_created", "uploaded_by"]:
            setattr(new_form, property, getattr(form_model_copy, property))
        new_form.save()
        
        # migrate related objects
        # these two classes are covered by reposting
        classes_not_to_touch = Metadata, ElementDefModel
        for cls, object_list in copies.items():
            if cls == FormDefModel or cls in classes_not_to_touch:
                continue
            
            # pull out all the appropriate foreign key fields
            fks = [field for field in cls._meta.fields \
                   if isinstance(field, ForeignKey) \
                   and field.rel.to in copies \
                   and not field.rel.to in classes_not_to_touch]
            
            for pk, obj in object_list.items():
                # blank out the pk/id and save to create new instances
                obj.id = None
                for fk in fks:
                    fk_value = getattr(obj, "%s_id" % fk.name)
                    # If this FK has been duplicated then point to the duplicate.
                    if fk_value in copies[fk.rel.to]:
                        dupe_obj = copies[fk.rel.to][fk_value]
                        setattr(obj, fk.name, dupe_obj)
                obj.save()
                
        # repost data
        for attachment_id in matching_meta_attachments:
            attach = Attachment.objects.get(id=attachment_id)
            self.save_form_data(attach)
        
        return new_form

    def _add_schema_from_file(self, file_name, domain=None):
        """ we keep this api open for the unit tests """
        name = os.path.basename(file_name)
        fin = open(file_name, 'r')
        ret = self.add_schema(name, fin, domain)
        fin.close()
        return ret

    def _save_schema_stream_to_file(self, stream, type):
        return self._save_schema_string_to_file(stream.read(), type)

    
    def _save_schema_string_to_file(self, input_data, type ):
        """Most of the 'new xform' functionality eventually ends up at this 
           method.  Given a string of xml and a type.  If the type is an
           XForm first saves the form to disk, then converts it to an .xsd
           file and also saves that.  If the type is already xsd, just saves
           it directly to disk.
           
           Returns the path to the newly created file."""
        transaction_str = str(uuid.uuid1())
        new_file_name = self._base_xsd_file_name(transaction_str)
        if type.lower() != "xsd":
            # assume this is an xhtml/xform file
            # first save the raw xform
            xform_filename = new_file_name + str(".xform")
            full_name = self._save_raw_data_to_file(xform_filename, input_data)
            schema,err,has_error = form_translate( input_data )
            if has_error:
                raise IOError, "Could not convert xform to schema." + \
                               " Please verify that this is a valid xform file."
        else:
            schema = input_data
        return self._save_raw_data_to_file(new_file_name, schema)
    
    def _save_raw_data_to_file(self, filename_base, data):
        """Save raw data to the xform manager's storage area.
           The filename used will be what is passed in.
           Returns the full name of the file that was written."""
        full_name = self._get_full_storage_location(filename_base)
        dest_file = open(full_name, 'w')
        dest_file.write(data)
        dest_file.close()
        return full_name
        
    def _save_raw_file_from_stream(self, filename_base, input_stream, buffer_size=1024*1024):
        """Save a raw stream to the xform manager's storage area.
           The filename used will be what is passed in.
           Returns the full name of the file that was written."""
        full_name = self._get_full_storage_location(filename_base)
        dest_file = open(full_name, 'w')
        while True:
            buffer = input_stream.read(buffer_size)
            if buffer:
                dest_file.write(buffer)
            else:
                break
        dest_file.close()
        input_stream.close()
        return full_name
        
    def _get_full_storage_location(self, filename_base):
        # Just a convenience passthrough to os.path.join()
        return os.path.join(self._get_storage_directory(),
                            filename_base)
        
    def _get_storage_directory(self):
        """Where this app keeps its files, which is specified in the config
           local.ini as 'xsd_repository_path'"""
        return settings.RAPIDSMS_APPS['xformmanager']['xsd_repository_path'] 
        
    def _xsd_file_name(self, base_name):
        return self.get_full_storage_location(self._get_storage_directory(), 
                                              self._base_xsd_file_name(base_name))
        
    def _base_xsd_file_name(self, base_name):
        return str(base_name) + '-xsd.xml'

class FormDefError(SyntaxError):
    """ Generic error for XFormManager.Manager """
    pass

def form_translate(input_data):
    '''Translates an xform into an xsd file'''
    return _form_translate(input_data, "schema")

def readable_form(input_data):
    '''Gets a readable display of an xform'''
    return _form_translate(input_data, "summary")


def csv_dump(input_data):
    '''Get the csv translation file from an xform'''
    return _form_translate(input_data, "csvdump")

def _form_translate(input_data, operation):
    """Utility for interacting with the form_translate jar, which provides 
       functionality for a number of different useful form tools including 
       converting a form to an xsd file, turning a form into a more readable
       format, and generating a list of translations as an exportable .csv
       file."""
    
    # In case you're trying to produce this behavior on the command line for
    # rapid testing, the command that eventually gets called is: 
    # java -jar form_translate.jar <operation> < form.xml > output
    #
    # You can pass in a filename or a full string/stream of xml data
    logging.debug ("form_translate %s: begin subprocess - java -jar form_translate.jar %s < input file > " \
                   % (operation, operation))
    p = subprocess.Popen(["java","-jar",
                          os.path.join(settings.RAPIDSMS_APPS['xformmanager']['xform_translate_path'],
                                       "form_translate.jar"),
                          operation], 
                          shell=False, 
                          stdout=subprocess.PIPE,stdin=subprocess.PIPE,
                          stderr=subprocess.PIPE)
    logging.debug ("form_translate %s: begin communicate with subprocess" % operation)
    
    p.stdin.write(input_data)
    p.stdin.flush()
    p.stdin.close()
    
    output = p.stdout.read()    
    error = p.stderr.read()
    
    # error has data even when things go perfectly, so return both
    # the full stream and a boolean indicating whether there was an
    # error.  This should be fixed in a cleaner way.
    has_error = "exception" in error.lower() 
    logging.debug ("form_translate %s: finish communicate with subprocess" % operation)
    return (output,error, has_error)
