from io import BytesIO

from OpenSSL import crypto
import uuid
from dateutil.parser import parse

from django.conf import settings
from django.http import HttpResponse

DEFAULT_EXPIRATION = 3 * 365 * 24 * 60 * 60  # three years in seconds


def create_key_pair():
    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 4096)
    return k


def create_self_signed_cert(key_pair, expiration_in_seconds=DEFAULT_EXPIRATION):
    cert = crypto.X509()
    cert.get_subject().C = "US"  # country
    cert.get_subject().ST = "MA"  # state
    cert.get_subject().L = "Cambridge"  # location
    cert.get_subject().O = "Dimagi Inc."  # organization
    cert.get_subject().OU = "CommCareHQ"  # organizational unit name
    cert.get_subject().CN = "CommCare"  # common name
    cert.get_subject().emailAddress = settings.ACCOUNTS_EMAIL
    cert.set_serial_number(uuid.uuid4().int)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(expiration_in_seconds)
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(key_pair)
    cert.sign(key_pair, "sha256")
    return cert


def get_expiration_date(cert):
    return parse(cert.get_notAfter())


def get_public_key(cert):
    return crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode("utf-8")


def get_private_key(key_pair):
    return crypto.dump_privatekey(crypto.FILETYPE_PEM, key_pair).decode("utf-8")


def get_certificate_from_file(file):
    return crypto.load_certificate(crypto.FILETYPE_PEM, file.read())


def get_certificate_response(cert_string, filename):
    response = HttpResponse(
        BytesIO(cert_string.encode("utf-8")),
        content_type="application/x-x509-user-cert"
    )
    response['Content-Disposition'] = f'attachment; filename={filename}'
    return response
