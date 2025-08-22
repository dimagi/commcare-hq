import hashlib

from django.contrib.auth.hashers import (
    BasePasswordHasher,
    mask_hash,
    must_update_salt,
)
from django.utils.crypto import constant_time_compare
from django.utils.translation import gettext_noop as _


class SHA1PasswordHasher(BasePasswordHasher):
    """
    The SHA1 password hashing algorithm (not recommended)

    Copied from django.contrib.auth.hashers because it was removed in v5.1.
    Use to upgrade historical password hashes to a more secure
    algorithm. Do not use as primary password hasher.
    """

    algorithm = "sha1"

    def encode(self, password, salt):
        self._check_encode_args(password, salt)
        hash = hashlib.sha1((salt + password).encode()).hexdigest()
        return "%s$%s$%s" % (self.algorithm, salt, hash)

    def decode(self, encoded):
        algorithm, salt, hash = encoded.split("$", 2)
        assert algorithm == self.algorithm
        return {
            "algorithm": algorithm,
            "hash": hash,
            "salt": salt,
        }

    def verify(self, password, encoded):
        decoded = self.decode(encoded)
        encoded_2 = self.encode(password, decoded["salt"])
        return constant_time_compare(encoded, encoded_2)

    def safe_summary(self, encoded):
        decoded = self.decode(encoded)
        return {
            _("algorithm"): decoded["algorithm"],
            _("salt"): mask_hash(decoded["salt"], show=2),
            _("hash"): mask_hash(decoded["hash"]),
        }

    def must_update(self, encoded):
        decoded = self.decode(encoded)
        return must_update_salt(decoded["salt"], self.salt_entropy)

    def harden_runtime(self, password, encoded):
        pass
