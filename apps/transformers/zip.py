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

# tarfile: using gzip vs. bzip2
# 60 seconds of googling leads me to believe bzip2 makes smaller files
# but takes more time. Feel free 2 change compression method if u know better.
def get_tarfile(file_list, output_file):
    """
    Create a tar file on disk                               
    """
    export_file = open( output_file, "w+b" )
    tar = tarfile.open(fileobj=export_file, mode="w:bz2")
    for file in file_list:
        tar.add(file, os.path.basename(file) )
    tar.close()
    wrapper = FileWrapper(export_file)
    response = HttpResponse(wrapper, content_type='application/tar')
    response['Content-Disposition'] = 'attachment; filename=commcarehq.tar'
    response['Content-Length'] = export_file.tell()
    # this seek is required for 'response' to work
    export_file.seek(0)    
    return response

class Compressor(object):
    def open(self, output_file):
        raise NotImplementedError()

    def add_stream(self, stream, size=0, name=None ):
        raise NotImplementedError()
    
    def close(self):
        raise NotImplementedError()
    
class TarCompressor(Compressor):
    def __init__(self):
        self._tar = None
    
    def open(self, output_file):
        self._tar = tarfile.open(fileobj=output_file, mode="w:bz2")

    def add_stream(self, stream, size=0, name=None):
        tar_info = tarfile.TarInfo(name=name )
        tar_info.size = size
        self._tar.addfile(tar_info, fileobj=stream)
    
    def close(self):
        self._tar.close()
