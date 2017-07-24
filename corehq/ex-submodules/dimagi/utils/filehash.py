import hashlib

def hash(filename, alg=hashlib.md5, block_size=2**20):
    with open(filename, "rb") as file:
        alg_instance = alg()
        while True:
            data = file.read(block_size)
            if not data:
                break
            alg_instance.update(data)
    return alg_instance

