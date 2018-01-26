from __future__ import absolute_import
import hashlib
from collections import OrderedDict
from django.contrib.auth.hashers import (
    BasePasswordHasher,
    SHA1PasswordHasher,
    mask_hash
)
from django.utils.encoding import force_bytes
from django.utils.crypto import constant_time_compare
from django.utils.translation import ugettext_noop as _


class CustomSHA256PasswordHasher(BasePasswordHasher):
    algorithm = "sha256hash"

    def encode(self, password, salt=None):
        """
        :param password: raw password
        :param salt: is not used
        :return: SHA256 hash
        """
        assert password is not None
        password_hash = hashlib.sha256(force_bytes(password)).hexdigest()
        return "%s$%s" % (self.algorithm, password_hash)

    def verify(self, sha256_encoded_sha256_password, sha256_password):
        """
        :param sha256_encoded_sha256_password: SHA256 encoded password,
        encoded with a salt using SHA256
        :param sha256_password: as in DB
        :return: boolean, password match or not
        """
        sha256_password_algorithm, sha256_password_hash = sha256_password.split('$', 1)
        if sha256_password_algorithm == SHA1PasswordHasher.algorithm:
            return SHA1PasswordHasher().verify(sha256_encoded_sha256_password, sha256_password)
        assert sha256_password_algorithm == self.algorithm

        algorithm, salt, hash = sha256_encoded_sha256_password.split('$', 2)

        assert algorithm == self.algorithm
        assert salt and '$' not in salt

        encoded_2 = hashlib.sha256(force_bytes(salt + sha256_password_hash)).hexdigest()
        return constant_time_compare(hash, encoded_2)

    def hashed_password(self, raw_password):
        sha256_password = hashlib.sha256(force_bytes(raw_password)).hexdigest()
        salt = self.salt()
        hash = hashlib.sha256(force_bytes(salt + sha256_password)).hexdigest()
        return "%s$%s$%s" % (self.algorithm, salt, hash)

    def safe_summary(self, encoded):
        algorithm, hash = encoded.split('$', 1)
        assert algorithm == self.algorithm
        return OrderedDict([
            (_('algorithm'), algorithm),
            (_('hash'), mask_hash(hash)),
        ])
