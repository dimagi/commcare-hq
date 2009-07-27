from xformmanager.storageutility import * 
import uuid
import subprocess
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

    def save_form_data(self, xml_file_name, submission):
        self.su.save_form_data(xml_file_name, submission)

    def add_schema(self, file_name, input_stream):
        transaction_str = str(uuid.uuid1())
        logging.debug("temporary file name is " + transaction_str)                
        new_file_name = self.__xsd_file_name(transaction_str)
        if file_name.endswith("xsd"):
            fout = open(new_file_name, 'w')
            fout.write( input_stream.read() )
            fout.close()
        else: 
            #user has uploaded an xhtml/xform file
            schema,err = form_translate( file_name, input_stream.read() )
            if err is not None:
                if err.lower().find("exception") != -1:
                    raise IOError, "XFORMMANAGER.VIEWS: problem converting xform to xsd: + " + file_name + "\nerror: " + str(err)
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
        new_file_name = self.__xsd_file_name(transaction_str)
        if type == "xsd":
            fout = open(new_file_name, 'w')
            fout.write( schema ) 
            fout.close()
        else: 
            schema,err = form_translate( file_name, schema )
            if err is not None:
                if err.lower().find("exception") != -1:
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
        formdefmodel = self.su.add_schema (formdef)
        formdefmodel.xsd_file_location = new_file_name
        formdefmodel.save()
        return formdefmodel

    def __xsd_file_name(self, name):
        return os.path.join(settings.rapidsms_apps_conf['xformmanager']['xsd_repository_path'], str(name) + '-xsd.xml')

def form_translate(name, input_stream):
    logging.debug ("XFORMMANAGER.VIEWS: begin subprocess - java -jar form_translate.jar schema < " + name + " > ")
    p = subprocess.Popen(["java","-jar",os.path.join(settings.rapidsms_apps_conf['xformmanager']['script_path'],"form_translate.jar"),'schema'], shell=False, stdout=subprocess.PIPE,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    logging.debug ("XFORMMANAGER.VIEWS: begin communicate with subprocess")
    
    #output,error = p.communicate( input_stream )    
    p.stdin.write(input_stream)
    p.stdin.flush()
    p.stdin.close()
    
    output = p.stdout.read()    
    error = p.stderr.read()
    
    logging.debug ("XFORMMANAGER.VIEWS: finish communicate with subprocess")
    return (output,error)