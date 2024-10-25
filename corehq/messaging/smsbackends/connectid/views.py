from Crypto.Cipher import AES
import base64

from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from corehq.apps.domain.auth import connectid_token_auth
from corehq.apps.users.models import ConnectIDMessagingKey, ConnectIDUserLink
from corehq.apps.sms.models import ConnectMessagingNumber, ConnectMessage, INCOMING
from corehq.apps.sms.api import process_incoming
from corehq.util.hmac_request import validate_request_hmac
from corehq.apps.mobile_auth.utils import generate_aes_key


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


@csrf_exempt
@connectid_token_auth
def connectid_messaging_key(request, domain):
    link = get_object_or_404(ConnectIDUserLink, commcare_user=request.user, domain=request.domain)
    key = generate_aes_key().decode("utf-8")
    messaging_key, _ = ConnectIDMessagingKey.objects.get_or_create(
        connectid_user_link=link, domain=request.domain, active=True, defaults={"key": key}
    )
    return JsonResponse({"key": messaging_key.key})


@csrf_exempt
@require_POST
@validate_request_hmac("CONNECTID_SECRET_KEY")
def update_connectid_messaging_consent(request, domain):
    username = request.POST.get("username")
    consent = request.POST.get("consent", False)
    if username is None:
        return HttpResponseBadRequest("ConnectId Username is required.")
    link = get_object_or_404(ConnectIDUserLink, connectid_username=username, domain=request.domain)
    link.messaging_consent = consent
    link.save()
    return HttpResponse(status=200)
