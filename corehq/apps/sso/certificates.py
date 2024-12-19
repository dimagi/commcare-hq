from datetime import datetime, timedelta, timezone
from io import BytesIO

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from django.conf import settings
from django.http import HttpResponse

DEFAULT_EXPIRATION = 3 * 365 * 24 * 60 * 60  # three years in seconds


def create_key_pair():
    return rsa.generate_private_key(public_exponent=65537, key_size=4096)


def create_self_signed_cert(key_pair, expiration_in_seconds=DEFAULT_EXPIRATION):
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "MA"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Cambridge"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Dimagi Inc."),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "CommCareHQ"),
        x509.NameAttribute(NameOID.COMMON_NAME, "CommCare"),
        x509.NameAttribute(NameOID.EMAIL_ADDRESS, settings.ACCOUNTS_EMAIL),
    ])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(seconds=expiration_in_seconds))
        .public_key(key_pair.public_key())
        .sign(key_pair, hashes.SHA256())
    )
    return cert


def get_expiration_date(cert):
    return cert.not_valid_after_utc


def get_public_key(cert):
    return cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")


def get_private_key(key_pair):
    return key_pair.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


def get_certificate_from_file(file):
    """Load certificate from file

    :raises: ValueError if the certificate is malformed. This is not
    documented in the reference[0], although the similarly named
    `load_pem_x509_certificates` is documented to raise ValueError.

    [0] https://cryptography.io/en/latest/x509/reference/#loading-certificates
    """
    return x509.load_pem_x509_certificate(file.read())


def get_certificate_response(cert_string, filename):
    response = HttpResponse(
        BytesIO(cert_string.encode("utf-8")),
        content_type="application/x-x509-user-cert"
    )
    response['Content-Disposition'] = f'attachment; filename={filename}'
    return response
