# encoding: utf-8
from unidecode import unidecode
from urllib import quote


def file_extention_from_filename(filename):
    extension = filename.rsplit('.', 1)[-1]
    if extension:
        return '.{}'.format(extension)
    return ''


def safe_for_fs(filename):
    """
    Returns a filename with FAT32-, NTFS- and HFS+-illegal characters removed.

    Unicode or bytestring datatype of filename is preserved.

    >>> safe_for_fs(u'spam*?: 𐍃𐍀𐌰𐌼-&.txt')
    u'spam 𐍃𐍀𐌰𐌼-&.txt'
    >>> safe_for_fs('spam*?: 𐍃𐍀𐌰𐌼-&.txt')
    'spam 𐍃𐍀𐌰𐌼-&.txt'
    """
    is_unicode = isinstance(filename, unicode)
    unsafe_chars = u':*?"<>|/\\\r\n' if is_unicode else ':*?"<>|/\\\r\n'
    empty = u'' if is_unicode else ''
    for c in unsafe_chars:
        filename = filename.replace(c, empty)
    return filename


def safe_filename_header(filename):
    # Removes illegal characters from filename and formats for 'Content-Disposition' HTTP header
    #
    # See IETF advice https://tools.ietf.org/html/rfc6266#appendix-D
    # and http://greenbytes.de/tech/tc2231/#attfnboth as a solution to disastrous browser compatibility

    filename = filename if isinstance(filename, unicode) else filename.decode('utf8')
    safe_filename = safe_for_fs(filename)
    ascii_filename = unidecode(safe_filename)
    return 'attachment; filename="{}"; filename*=UTF-8\'\'{}'.format(
        ascii_filename, quote(safe_filename.encode('utf8')))
