from unittest.mock import Mock, patch

from .. import two_factor_gateways as mod


def test_gateway_make_call():
    gateway = mod.Gateway.__new__(mod.Gateway)  # instantiate without __init__
    gateway.from_number = "+16145551234"
    gateway.client = Mock(name="client")
    device = Mock(name="device")
    device.number.as_e164 = "+14155552671"
    with patch.object(mod, "Site") as Site:
        Site.objects.get_current().domain = "test.com"
        gateway.make_call(device, "70839")
    gateway.client.api.account.calls.create.assert_called_with(
        to="+14155552671",
        from_="+16145551234",
        url="https://test.com/twilio/inbound/two_factor/70839/?locale=en-us",
        method="GET",
        if_machine="Hangup",
        timeout=15,
    )
