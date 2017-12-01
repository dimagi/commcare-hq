# encoding: utf-8
from __future__ import absolute_import
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
        filename = u"{}.{}".format(filename, extension)
    unsafe_chars = u':*?"<>|/\\\r\n'
    for c in unsafe_chars:
        filename = filename.replace(c, u'')
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
