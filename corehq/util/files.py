# encoding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
import os
import tempfile
from unidecode import unidecode
from six.moves.urllib.parse import quote
import six


def file_extention_from_filename(filename):
    extension = filename.rsplit('.', 1)[-1]
    if extension:
        return '.{}'.format(extension)
    return ''


def safe_filename(filename, extension=None):
    """
    Returns a filename with FAT32-, NTFS- and HFS+-illegal characters removed.

    Unicode or bytestring datatype of filename is preserved.

    >>> safe_filename(u'spam*?: 𐍃𐍀𐌰𐌼-&.txt')
    u'spam 𐍃𐍀𐌰𐌼-&.txt'
    """
    filename = filename if isinstance(filename, six.text_type) else filename.decode('utf8')
    if extension is not None:
        filename = "{}.{}".format(filename, extension)
    unsafe_chars = ':*?"<>|/\\\r\n'
    for c in unsafe_chars:
        filename = filename.replace(c, '')
    return filename


def safe_filename_header(filename, extension=None):
    # Removes illegal characters from filename and formats for 'Content-Disposition' HTTP header
    #
    # See IETF advice https://tools.ietf.org/html/rfc6266#appendix-D
    # and http://greenbytes.de/tech/tc2231/#attfnboth as a solution to disastrous browser compatibility
    filename = safe_filename(filename, extension)
    ascii_filename = unidecode(filename)
    return 'attachment; filename="{}"; filename*=UTF-8\'\'{}'.format(
        ascii_filename, quote(filename.encode('utf8')))


class TransientTempfile(object):
    """
    Manage a temporary file that can be opened and closed as needed, but will
    be automatically cleaned up on failure or exit.

        with TransientTempfile() as path:
            # path exists throughout this block
            with open(path, 'w') as f:
                f.write("Adding stuff to the file")
            with open(path) as f:
                do_stuff(f.read())
        # path no longer exists
    """

    def __enter__(self):
        fd, self.path = tempfile.mkstemp()
        os.close(fd)
        return self.path

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.remove(self.path)


def read_workbook_content_as_file(wb):
    with tempfile.TemporaryFile() as temp_file:
        wb.save(temp_file)
        temp_file.seek(0)
        return temp_file.read()
