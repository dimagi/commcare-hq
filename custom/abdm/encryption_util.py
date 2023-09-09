import base64
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from custom.abdm.fidelius_encryption_util import decryptData
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

CRYPTO_ALGORITHM = 'ECDH'
CURVE = 'Curve25519'
AES_KEY_LENGTH = 32
NONCE_LENGTH = 32


def generate_key_material():
    private_key = X25519PrivateKey.generate()
    # private_key_b64 = private_key.private_bytes()
    public_key_b64_str = base64.b64encode((private_key.public_key()).public_bytes_raw()).decode()
    # public_key_b64_str = base64.b64encode((private_key.public_key()).public_bytes(encoding=Encoding.DER,
    #                                                                               format=PublicFormat.SubjectPublicKeyInfo)).decode()
    a = int.from_bytes(private_key.public_key().public_bytes_raw(), 'little')
    public_key_b64_str = base64.b64encode(a.to_bytes((a.bit_length() + 7) // 8, 'big')).decode()
    # TODO Figure out for x509_public_key
    x509_public_key = public_key_b64_str
    nonce_b64_str = base64.b64encode(os.urandom(NONCE_LENGTH)).decode()
    return private_key, public_key_b64_str, x509_public_key, nonce_b64_str


def compute_shared_key(public_key_b64_str, private_key):
    public_key_bytes = base64.b64decode(public_key_b64_str)
    print(f"length of public_key_bytes: {len(public_key_bytes)}")
    if len(public_key_bytes) == 65:
        x_public_key = public_key_bytes[1:33]
        public_key = X25519PublicKey.from_public_bytes(x_public_key)
    else:
        public_key = X25519PublicKey.from_public_bytes(public_key_bytes)
    return private_key.exchange(public_key)


def calculate_salt_iv(nonce1_b64_str, nonce2_b64_str):
    xor_of_nonces = bytes(a ^ b for (a, b) in zip(nonce1_b64_str.encode(), nonce2_b64_str.encode()))
    salt = xor_of_nonces[:20]
    iv = xor_of_nonces[-12:]
    return salt, iv


def compute_aes_key(salt, shared_key):
    return HKDF(
        algorithm=hashes.SHA256(),
        length=AES_KEY_LENGTH,
        salt=salt,
        info=None,
    ).derive(shared_key)


def encrypt(data, aes_key, iv):
    cipher = Cipher(algorithms.AES(aes_key), modes.GCM(iv))
    encryptor = cipher.encryptor()
    return encryptor.update(data.encode()) + encryptor.finalize()


def decrypt(data, aes_key, iv):
    cipher = Cipher(algorithms.AES(aes_key), modes.GCM(iv))
    decryptor = cipher.decryptor()
    return decryptor.update(data).decode()


# TODO Move this to tests
def run_example():
    from custom.abdm.encryption_util2 import getEcdhKeyMaterial
    # HIU Side
    # hiu_private_key, hiu_public_key, hiu_x509_public_key, hiu_nonce = generate_key_material()
    # # Save all in db and share hiu_x509_public_key and hiu_nonce to HIPf

    hiu_key_material = getEcdhKeyMaterial()
    hiu_x509_public_key = hiu_key_material['publicKey']
    hiu_nonce = hiu_key_material['nonce']
    hiu_private_key = hiu_key_material['privateKey']
    print(f"Sending to HIP hiu_x509_public_key: {hiu_x509_public_key} , hiu_nonce: {hiu_nonce} "
          f"and data push url: https://hiu/data")


    # HIP Side
    data = 'Hey I am a secret!'
    print(f"Data to be encrypted: {data}")
    hip_private_key, hip_public_key, hip_x509_public_key, hip_nonce = generate_key_material()
    print(f"length of hip_public_key : {len(hip_public_key)}")
    salt, iv = calculate_salt_iv(hip_nonce, hiu_nonce)
    shared_key = compute_shared_key(hiu_x509_public_key, hip_private_key)
    aes_key = compute_aes_key(salt, shared_key)
    encrypted_data = base64.b64encode(encrypt(data, aes_key, iv)).decode()
    print(f"Sending to HIU hip_public_key: {hip_public_key}, hip_nonce: {hip_nonce}"
          f" and encrypted_data: {encrypted_data}")

    # HIU Side
    # Get key material from database for the said transaction
    # salt, iv = calculate_salt_iv(hip_nonce, hiu_nonce)
    # shared_key = compute_shared_key(hip_x509_public_key, hiu_private_key)
    # aes_key = compute_aes_key(salt, shared_key)
    # decrypted_data = decrypt(encrypted_data, aes_key, iv)
    # print(f"decrypted_data: {decrypted_data}")

    decryptionResult = decryptData({
        'encryptedData': encrypted_data,
        'requesterNonce': hiu_nonce,
        'senderNonce': hip_nonce,
        'requesterPrivateKey': hiu_private_key,
        'senderPublicKey': hip_public_key
    })


if __name__ == '__main__':
    run_example()
