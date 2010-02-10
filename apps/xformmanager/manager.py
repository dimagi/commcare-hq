from xformmanager.storageutility import * 
from xformmanager.xformdef import FormDef
from xformmanager.models import MetaDataValidationError
import uuid
import subprocess
from subprocess import PIPE

class XFormManager(object):
    """ This class makes the process of handling formdefs (our 
    representation of schemas) and formdefmodels (db interaction layer),
    completely transparent to the programmers
    """
    def __init__(self):
        self.su  = StorageUtility()

    def remove_schema(self, id, remove_submissions=False):
        self.su.remove_schema(id, remove_submissions)    

    def remove_data(self, formdef_id, id, remove_submission=False):
        self.su.remove_instance_matching_schema(formdef_id, id, remove_submission)
        
    def save_schema_POST_to_file(self, stream, file_name):
        """ save POST to file """
        try:
            type = file_name.rsplit('.',1)[1]
        except IndexError:
            # POSTed file has no extension
            type = "xform"
        filename_on_disk = self._save_schema_stream_to_file(stream, type)
        return filename_on_disk

    def save_form_data(self, xml_file_name, attachment):
        """ return True on success and False on fail """
        return self.su.save_form_data(xml_file_name, attachment)
    
    def validate_schema(self, file_name):
        """validate schema 
           Returns a tuple (is_valid, error)
           is_valid - True if valid, False if not
           error - Relevant validation error
        """
        #process xsd file to FormDef object
        fout = open(file_name, 'r')
        formdef = FormDef(fout)
        fout.close()
        
        try:
            formdef.validate()
        except Exception, e:
            return False, e
        return True, None

    def create_schema_from_file(self, new_file_name):
        """ process schema """
        #process xsd file to FormDef object
        fout = open(new_file_name, 'r')
        formdef = FormDef(fout)
        fout.close()
        formdefmodel = self.su.add_schema (formdef)
        formdefmodel.xsd_file_location = new_file_name
        formdefmodel.save()
        return formdefmodel

    def add_schema_manually(self, schema, type):
        """ manually register a schema """
        file_name = self._save_schema_string_to_file(schema, type)
        return self.create_schema_from_file(file_name)

    def add_schema(self, file_name, input_stream):
        """ we keep this api open for the unit tests """
        file_name = self.save_schema_POST_to_file(input_stream, file_name)
        return self.create_schema_from_file(file_name)
    
    def _add_schema_from_file(self, file_name):
        """ we keep this api open for the unit tests """
        name = os.path.basename(file_name)
        fin = open(file_name, 'r')
        ret = self.add_schema(name, fin)
        fin.close()
        return ret

    def _save_schema_stream_to_file(self, stream, type):
        return self._save_schema_string_to_file(stream.read(), type)

    
    def _save_schema_string_to_file(self, input_data, type ):
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
        """Where this app keeps its files"""
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
    """Utility for interacting with the form_translate jar"""
    # java -jar form_translate.jar csvdump < form.xml > output
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
