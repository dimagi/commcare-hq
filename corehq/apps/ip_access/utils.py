import ipaddress

ORIGIN_IP_HEADER = 'HTTP_X_COMMCAREHQ_ORIGIN_IP'


def get_origin_ip(request):
    """
    Returns the Web Apps client's IP address as forwarded by formplayer in
    the ``X-CommCareHQ-Origin-IP`` header, or ``None`` if the header is
    absent or does not start with an IP address.

    Formplayer forwards the value of ``X-Forwarded-For`` verbatim, which
    may be a comma-separated list; the first entry is the client.

    Callers must only trust the header on requests they have verified came
    from formplayer.
    """
    header_value = request.META.get(ORIGIN_IP_HEADER, '')
    candidate = header_value.split(',', 1)[0].strip()
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None
