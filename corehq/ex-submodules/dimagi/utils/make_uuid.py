from __future__ import absolute_import
import random


def random_hex():
    return hex(random.getrandbits(160))[2:-1]
