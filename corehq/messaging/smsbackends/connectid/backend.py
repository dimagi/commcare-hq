import base64
import requests
from Crypto.Cipher import AES
from uuid import uuid4

from django.conf import settings

from corehq.apps.users.models import ConnectIDUserLink, CouchUser

class ConnectBackend:
    def send(self, message):
        user = CouchUser.get_by_user_id(message.couch_recipient).django_user
        user_link = ConnectIDUserLink.objects.get(commcare_user=user)
        key = base64.b64decode(user_link.conectidmessagingkey_set.first())
        cipher = AES.new(key, AES.MODE_GCM)
        data, tag = cipher.encrypt_and_digest(message.text.encode("utf-8"))
        content = {
            "tag": tag,
            "nonce": cipher.nonce,
            "ciphertext": data,
        }
        requests.post(
            settings.CONNECTID_MESSAGE_URL,
            data={
                "channel": user_link.channel_id,
                "content": content,
                "message_id": uuid4(),
            },
            headers={"Authorization": f"Basic {settings.CONNECTID_CLIENT_ID}:{settings.CONNECTID_SECRET_KEY}"}
        )

    def create_channel(self, user):
        user_link = ConnectIDUserLink.objects.get(commcare_user=user)
        response = requests.post(
            settings.CONNECTID_CHANNEL_URL,
            data={
                "connectid": connectid_username,
                "channel_source": user_link.domain,
            },
            headers={"Authorization": f"Basic {settings.CONNECTID_CLIENT_ID}:{settings.CONNECTID_SECRET_KEY}"}
        )
        user_link.channel_id = response.json()["channel_id"]
        user_link.save()
