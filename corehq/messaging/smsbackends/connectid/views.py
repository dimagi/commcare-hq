from Crypto.Cipher import AES
import base64
import json

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

@csrf_exempt
@require_POST
@validate_request_hmac("CONNECTID_SECRET_KEY")
def receive_message(request, *args, **kwargs):
    data = json.loads(request.body.decode("utf-8"))
    channel_id = data["channel"]
    user_link = ConnectIDUserLink.objects.get(channel_id=channel_id)
    phone_obj = ConnectMessagingNumber(user_link)
    for message in data["messages"]:
        content = data["content"]
        key = base64.b64decode(user_link.conectidmessagingkey_set.first())
        cipher = AES.new(key, AES.MODE_GCM, nonce=content["nonce"])
        text = cipher.decrypt_and_verify(content["ciphertext"], content["tag"]).decode("utf-8")
        timestamp = data["timestamp"]
        message_id = data["message_id"]
        msg = ConnectMessage(
            direction=INCOMING,
            date=timestamp,
            text=text,
            domain_scope=user_link.domain,
            backend_id="connectid",
            message_id=message_id
        )
        process_incoming(msg, phone_obj)
    return HttpResponse(status=200)


@csrf_exempt
@require_POST
@connectid_token_auth
def connectid_messaging_key(request, *args, **kwargs):
    channel_id = request.POST.get("channel_id")
    if channel_id is None:
        return HttpResponseBadRequest("Channel ID is required.")
    link = get_object_or_404(ConnectIDUserLink, channel_id=channel_id)
    key = generate_aes_key().decode("utf-8")
    messaging_key, _ = ConnectIDMessagingKey.objects.get_or_create(
        connectid_user_link=link, domain=link.domain, active=True, defaults={"key": key}
    )
    return JsonResponse({"key": messaging_key.key})


@csrf_exempt
@require_POST
@validate_request_hmac("CONNECTID_SECRET_KEY")
def update_connectid_messaging_consent(request, *args, **kwargs):
    data = json.loads(request.body)
    channel_id = data.get("channel_id")
    consent = data.get("consent", False)
    if channel_id is None:
        return HttpResponseBadRequest("Channel ID is required.")
    link = get_object_or_404(ConnectIDUserLink, channel_id=channel_id)
    link.messaging_consent = consent
    link.save()
    return HttpResponse(status=200)


@csrf_exempt
@require_POST
@validate_request_hmac("CONNECTID_SECRET_KEY")
def messaging_callback_url(request, *args, **kwargs):
    data = json.loads(request.body.decode("utf-8"))
    channel_id = data.get("channel_id")
    if channel_id is None:
        return HttpResponseBadRequest("Channel ID is required.")
    user_link = get_object_or_404(ConnectIDUserLink, channel_id=channel_id)
    messages = data.get("messages", [])
    messages_to_update = []
    message_data = {message.get("message_id"): message.get("received_on") for message in messages}
    message_ids = list(message_data.keys())
    message_objs = ConnectMessage.objects.filter(
        message_id__in=message_ids,
        domain=user_link.domain,
        backend_id="connectid"
    )
    for message_obj in message_objs:
        received_on = message_data.get(message_obj.message_id)
        if received_on is None:
            continue
        message_obj.received_on = received_on
        messages_to_update.append(message_obj)
    ConnectMessage.objects.bulk_update(messages_to_update, ("received_on",))
    return HttpResponse(status=200)
