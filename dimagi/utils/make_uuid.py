import random
import uuid

def make_uuid():
    return uuid.uuid1().hex

def random_hex():
    return hex(random.getrandbits(160))[2:-1]