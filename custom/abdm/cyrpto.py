import hashlib
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

from base64 import b64encode
from custom.abdm.fidelius_encryption_util import getEcdhKeyMaterial, encryptData, decryptData

CRYPTO_ALGORITHM = 'ECDH'
CURVE = 'Curve25519'
KEY_MATERIAL_EXPIRY = 30 * 60   # in seconds


class ABDMCrypto:
    """
    Wrapper class to perform cryptography operations as per ABDM policy
    """
    # TODO Add Error Handling

    def __init__(self, key_material_json=None):
        self.key_material = KeyMaterial.from_dict(key_material_json) if key_material_json \
            else self._generate_key_material()
        self.transfer_material = self.key_material.get_transfer_material()

    @staticmethod
    def _generate_key_material():
        key_material = getEcdhKeyMaterial()
        return KeyMaterial(
            public_key=key_material['publicKey'],
            private_key=key_material['privateKey'],
            nonce=key_material['nonce'],
            x509_public_key=key_material['x509PublicKey'],
        )

    def encrypt(self, data, peer_transfer_material):
        result = encryptData(
            {
                'stringToEncrypt': data,
                'senderNonce': self.key_material.nonce,
                'requesterNonce': peer_transfer_material['nonce'],
                'senderPrivateKey': self.key_material.private_key,
                'requesterPublicKey': peer_transfer_material['dhPublicKey']['keyValue']
            })
        return result['encryptedData']

    def decrypt(self, data, peer_transfer_material):
        result = decryptData(
            {
                'encryptedData': data,
                'requesterNonce': self.key_material.nonce,
                'senderNonce': peer_transfer_material['nonce'],
                'requesterPrivateKey': self.key_material.private_key,
                'senderPublicKey': peer_transfer_material['dhPublicKey']['keyValue']
            })
        return result['decryptedData']

    @staticmethod
    def generate_checksum(data):
        return b64encode(hashlib.md5(data.encode('utf-8')).digest()).decode()


@dataclass(frozen=True)
class KeyMaterial:
    public_key: str
    private_key: str
    nonce: str
    x509_public_key: str

    @staticmethod
    def from_dict(data):
        return KeyMaterial(
            public_key=data['public_key'],
            private_key=data['private_key'],
            nonce=data['nonce'],
            x509_public_key=data['x509_public_key'],
        )

    def as_dict(self):
        return asdict(self)

    def get_transfer_material(self):
        """
        Converts into a format as per ABDM policy
        """
        return {
            "cryptoAlg": CRYPTO_ALGORITHM,
            "curve": CURVE,
            "dhPublicKey": {
                "expiry": (datetime.utcnow() + timedelta(seconds=KEY_MATERIAL_EXPIRY)).isoformat(),
                "parameters": "Curve25519",
                "keyValue": self.public_key
            },
            "nonce": self.nonce
        }
