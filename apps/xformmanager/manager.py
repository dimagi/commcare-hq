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

    def remove_schema(self, id):
        self.su.remove_schema(id)    

    def remove_data(self, formdef_id, id):
        self.su.remove_instance_matching_schema(formdef_id, id)

    def save_form_data(self, xml_file_name, submission):
        """ return True on success and False on fail """
        return self.su.save_form_data(xml_file_name, submission)
        
    def add_schema(self, file_name, input_stream):
        transaction_str = str(uuid.uuid1())
        logging.debug("temporary file name is " + transaction_str)                
        new_file_name = self._xsd_file_name(transaction_str)
        if file_name.endswith("xsd"):
            fout = open(new_file_name, 'w')
            fout.write( input_stream.read() )
            fout.close()
        else: 
            #user has uploaded an xhtml/xform file
            schema,err,has_error = form_translate( file_name, input_stream.read() )
            if has_error:
                raise IOError, ("Could not convert xform (%s) to schema." % file_name) + \
                                " Please verify that this is a valid xform file."
            fout = open(new_file_name, 'w')
            fout.write( schema )
            fout.close()
        return self._create_schema_from_temp_file(new_file_name)

    def add_schema_manual(self, schema, type):
        '''A fairly duplicated API of add_schema to support passing 
           in the schema an in-memory string, and including some metadata
           with it.  These two methods should be merged.'''
        transaction_str = str(uuid.uuid1())
        logging.debug("temporary file name is " + transaction_str)                
        new_file_name = self._xsd_file_name(transaction_str)
        if type == "xsd":
            fout = open(new_file_name, 'w')
            fout.write( schema ) 
            fout.close()
        else: 
            schema,err,has_error = form_translate( file_name, schema )
            if has_error:
                raise IOError, "XFORMMANAGER.VIEWS: problem converting xform to xsd: + " + file_name + "\nerror: " + str(err)
            fout = open(new_file_name, 'w')
            fout.write( schema )
            fout.close()
        return self._create_schema_from_temp_file(new_file_name)
        
    def _create_schema_from_temp_file(self, new_file_name):
        #process xsd file to FormDef object
        fout = open(new_file_name, 'r')
        formdef = FormDef(fout)
        fout.close()
        
        # This is taken directly from buildmanager.jar.validate_jar
        # replicated here since we expect different behaviour on the 
        # different error conditions (i.e. XFormManager.Errors instead of
        # BuildErrors
        # </copy>
        
        # check xmlns not none
        if not formdef.target_namespace:
            raise FormDefError("No namespace found in submitted form. Form saved to %s" % new_file_name)
        
        # all the forms in use today have a superset namespace they default to
        # something like: http://www.w3.org/2002/xforms
        if formdef.target_namespace.lower().find('www.w3.org') != -1:
            raise FormDefError("No namespace found in submitted form. Form saved to %s" % new_file_name)

        meta_element = formdef.get_meta_element()
        if not meta_element:
            raise FormDefError("From has no meta block! Saved to %s" % new_file_name)
        
        meta_issues = FormDef.get_meta_validation_issues(meta_element)
        if meta_issues:
            mve = MetaDataValidationError(meta_issues, new_file_name)
            # until we have a clear understanding of how meta versions will work,
            # don't fail on issues that only come back with "extra" set.  i.e.
            # look for missing or duplicate
            if mve.duplicate or mve.missing:
                raise mve
            else:
                logging.warning("Found extra meta fields in form. Form saved to %s, %s" % \
                                (new_file_name, mve.extra))
        # </copy>
                
        formdefmodel = self.su.add_schema (formdef)
        formdefmodel.xsd_file_location = new_file_name
        formdefmodel.save()
        return formdefmodel

    def _xsd_file_name(self, name):
        return os.path.join(settings.RAPIDSMS_APPS['xformmanager']['xsd_repository_path'], 
                            str(name) + '-xsd.xml')

class FormDefError(SyntaxError):
    """ Generic error for XFormManager.Manager """
    pass

def form_translate(name, input_stream):
    '''Translates an xform into an xsd file'''
    logging.debug ("XFORMMANAGER.VIEWS: begin subprocess - java -jar form_translate.jar schema < " + name + " > ")
    p = subprocess.Popen(["java","-jar",os.path.join(settings.RAPIDSMS_APPS['xformmanager']['xform_translate_path'],"form_translate.jar"),'schema'], shell=False, stdout=subprocess.PIPE,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    logging.debug ("XFORMMANAGER.VIEWS: begin communicate with subprocess")
    
    p.stdin.write(input_stream)
    p.stdin.flush()
    p.stdin.close()
    
    output = p.stdout.read()    
    error = p.stderr.read()
    
    # error has data even when things go perfectly, so return both
    # the full stream and a boolean indicating whether there was an
    # error.  This should be fixed in a cleaner way.
    has_error = "exception" in error.lower() 
    logging.debug ("XFORMMANAGER.VIEWS: finish communicate with subprocess")
    return (output,error, has_error)
