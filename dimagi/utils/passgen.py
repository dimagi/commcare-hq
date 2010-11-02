#!/usr/bin/python

import math
import random
from optparse import OptionParser

# no need to seed random; automatically seeded on import from OS entropy
# source

alphabet = 'abcdefghijklmnopqrstuvwxyz0123456789'
# why no CAPS??
#
# including capital letters achieves more bits of entropy per character,
# but for a password of given entropy, actually requires more typing overall
#
# lowercase alphanumerics contain 5.17 bits of entropy per character.
# mixed-case alphanumerics have 5.95 bits/char. thus, passwords of similar
# strength will be 15% longer using only lowercase.
#
# however, typing a mixed-case random string of length n will on average
# require .244n pressings of the shift key. so that 15% shorter password
# will actually require 8% more keystrokes.
#
# just use lowercase and pick password length based on entropy, not
# character count

def rand_pass(n):
    return ''.join(random.choice(alphabet) for i in range(0, n))

def entropy_per_char():
    return math.log(len(alphabet)) / math.log(2.)

def chars_for_entropy(bits):
    return int(math.ceil(bits / entropy_per_char()))

def entropy_for_length(length):
    return entropy_per_char() * length

def make_password(length=None, entropy=None):
    ent_length = chars_for_entropy(entropy) if entropy else 0
    length = max(ent_length, length) if length else ent_length
    return rand_pass(length)

if __name__ == '__main__':
    DEFAULT_ENTROPY = 32

    parser = OptionParser()
    parser.add_option('-e', '--entropy', '-b', '--bits', metavar='#bits',
                      dest='entropy', type='float',
                      help='minimum password entropy (in bits)')
    parser.add_option('-l', '--length', '-c', '--chars', metavar='#chars',
                      dest='length', type='int',
                      help='password length (in chars)')

    (op, _) = parser.parse_args()
    if not op.length and not op.entropy:
        op.entropy = DEFAULT_ENTROPY

    passwd = make_password(length=op.length, entropy=op.entropy)

    print '%s (length: %d; %.1fb entropy)' % (passwd, len(passwd), entropy_for_length(len(passwd)))
