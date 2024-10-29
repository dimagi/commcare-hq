from Crypto.Cipher import AES
import base64

from django.http import HttpResponse

from corehq.apps.users.models import ConnectIDUserLink
from corehq.apps.sms.models import ConnectMessagingNumber, ConnectMessage, INCOMING
from corehq.apps.sms.api import process_incoming


def receive_message(request, *args, **kwargs):
    data = request.POST
    channel_id = data["channel_id"]
    user_link = ConnectIDUserLink.objects.get(channel_id=channel_id)
    phone_obj = ConnectMessagingNumber(user_link)
    content = data["content"]
    key = base64.b64decode(user_link.conectidmessagingkey_set.first())
    cipher = AES.new(key, AES.MODE_GCM, nonce=content["nonce"])
    text = cipher.decrypt_and_verify(content["ciphertext"], content["tag"]).decode("utf-8")
    timestamp = data["timestamp"]
    msg = ConnectMessage(
        direction=INCOMING,
        date=timestamp,
        text=text,
        domain_scope=user_link.domain,
        backend_id="connectid"
    )
    process_incoming(msg, phone_obj)
    return HttpResponse("")
