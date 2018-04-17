# http://rosettacode.org/wiki/LZW_compression#Python
from __future__ import absolute_import
from __future__ import unicode_literals
import io
import six
from six.moves import range


def decompress(compressed):
    """Decompress a list of output ks to a string."""

    # Build the dictionary.
    dict_size = 0x10000
    dictionary = dict((six.chr(i), six.chr(i)) for i in range(dict_size))

    result = io.StringIO()
    w = compressed.pop(0)
    result.write(w)
    for k in compressed:
        if k in dictionary:
            entry = dictionary[k]
        elif k == dict_size:
            entry = w + w[0]
        else:
            raise ValueError('Bad compressed k: %s' % k)
        result.write(entry)

        # Add w+entry[0] to the dictionary.
        dictionary[dict_size] = w + entry[0]
        dict_size += 1

        w = entry
    return result.getvalue()
