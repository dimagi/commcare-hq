import base64
import requests
from Crypto.Cipher import AES

from django.conf import settings

from corehq.apps.users.models import ConnectIDUserLink, CouchUser


class ConnectBackend:
    couch_id = "connectid"
    opt_out_keywords = []
    opt_in_keywords = []

    def send(self, message):
        user = CouchUser.get_by_user_id(message.couch_recipient).get_django_user()
        user_link = ConnectIDUserLink.objects.get(commcare_user=user)

        # create channel if it does not yet exist
        if not user_link.channel_id:
            self.create_channel(user_link)
            user_link.refresh_from_db()

        raw_key = user_link.messaging_key.key
        key = base64.b64decode(raw_key)
        cipher = AES.new(key, AES.MODE_GCM)
        data, tag = cipher.encrypt_and_digest(message.text.encode("utf-8"))
        content = {
            "tag": base64.b64encode(tag).decode("utf-8"),
            "nonce": base64.b64encode(cipher.nonce).decode("utf-8"),
            "ciphertext": base64.b64encode(data).decode("utf-8"),
        }
        response = requests.post(
            settings.CONNECTID_MESSAGE_URL,
            json={
                "channel": user_link.channel_id,
                "content": content,
                "message_id": str(message.message_id),
            },
            auth=(settings.CONNECTID_CLIENT_ID, settings.CONNECTID_SECRET_KEY)
        )
        return response.status_code == requests.codes.OK

    def create_channel(self, user_link):
        response = requests.post(
            settings.CONNECTID_CHANNEL_URL,
            data={
                "connectid": user_link.connectid_username,
                "channel_source": user_link.domain,
            },
            auth=(settings.CONNECTID_CLIENT_ID, settings.CONNECTID_SECRET_KEY)
        )
        if response.status_code == 404:
            return False
        response_dict = response.json()
        user_link.channel_id = response_dict["channel_id"]
        user_link.messaging_consent = response_dict["consent"]
        user_link.save()
        return True
