import hashlib

def hash(filename, alg=hashlib.md5, block_size=2**20):
    file = open(filename, "rb")
    alg_instance = alg()
    while True:
        data = file.read(block_size)
        if not data:
            break
        alg_instance.update(data)
    file.close()
    return alg_instance

