import os, tempfile, zipfile, tarfile, logging
from django.core.servers.basehttp import FileWrapper
from django.http import HttpResponse

def get_zipfile(file_list):
    """
    Create a ZIP file on disk and transmit it in chunks of 8KB,                 
    without loading the whole file into memory.        
    """
    temp = tempfile.TemporaryFile()
    archive = zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED)
    for file in file_list:
        file = file.encode("utf-8")
        if os.path.exists(file):
            archive.write(file, os.path.basename(file))
        else:
            logging.warn("zipfile could not find %s" % file)
    archive.close()
    wrapper = FileWrapper(temp)
    response = HttpResponse(wrapper, content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename=commcarehq.zip'
    response['Content-Length'] = temp.tell()
    # this seek is required for 'response' to work
    temp.seek(0)    
    return response

def build_tarfile(file_list, output_file):
    """
    Creates a tarfile on disk, given a list of input files
    """
    tar = tarfile.open(name=output_file, mode="w:bz2")
    if len (file_list) == 0:
        logging.info("No submissions could be found.")
        return HttpResponse("No submissions could be found.")
    for file in file_list:
        tar.add(file, os.path.basename(file) )
    tar.close()
    return tar

def get_tarfile(file_list, output_file):
    """
    Creates a tarfile on disk, given a list of input files, 
    and returns it as an http response.
    """
    tar = build_tarfile(file_list, output_file)
    fin = open(output_file, 'rb')
    wrapper = FileWrapper(fin)
    response = HttpResponse(wrapper, content_type='application/tar')
    response['Content-Disposition'] = 'attachment; filename=commcarehq.tar'
    response['Content-Length'] = os.path.getsize(output_file)
    # this seek is required for 'response' to work
    return response

class Compressor(object):
    """ Interface to create a compressed file on disk, given streams """
    def open(self, output_file):
        raise NotImplementedError()

    def add_stream(self, stream, size=0, name=None ):
        raise NotImplementedError()
    
    def close(self):
        raise NotImplementedError()
    
class TarCompressor(Compressor):
    """ Interface to create a tarfile on disk, given various input streams """

    def __init__(self):
        self._tar = None
    
    def open(self, name=None, fileobj=None):
        if name == None and fileobj == None:
            raise ValueError('Either name or fileobj must be supplied to TarCompressor')
        self._tar = tarfile.open(name=name, fileobj=fileobj, mode="w:bz2")

    def add_stream(self, stream, size=0, name=None):
        tar_info = tarfile.TarInfo( name=name )
        tar_info.size = size
        self._tar.addfile(tar_info, fileobj=stream)
    
    def add_file(self, file):
        self._tar.add(file, os.path.basename(file))
    
    def close(self):
        self._tar.close()
