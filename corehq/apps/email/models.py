from django.db import models

from corehq.motech.const import PASSWORD_PLACEHOLDER, ALGO_AES
from corehq.motech.utils import b64_aes_decrypt, b64_aes_encrypt


class EmailSettings(models.Model):
    domain = models.CharField(max_length=255, unique=True)
    username = models.CharField(max_length=255)
    password = models.CharField(max_length=255)
    server = models.CharField(max_length=255)
    port = models.IntegerField(default=0)
    from_email = models.EmailField()
    return_path_email = models.EmailField(default='')
    use_this_gateway = models.BooleanField(default=False)
    use_tracking_headers = models.BooleanField(default=False)
    sns_secret = models.CharField(max_length=100)
    ses_config_set_name = models.CharField(max_length=100)

    def __str__(self):
        fields = vars(self)
        field_str = ", ".join([f"{key}: {value}" for key, value in fields.items() if not key.startswith("_")])
        return f"<EmailSettings> - {field_str}"

    @property
    def plaintext_password(self):
        if self.password.startswith(f'${ALGO_AES}$'):
            ciphertext = self.password.split('$', 2)[2]
            return b64_aes_decrypt(ciphertext)
        return self.password

    @plaintext_password.setter
    def plaintext_password(self, plaintext):
        if plaintext != PASSWORD_PLACEHOLDER:
            ciphertext = b64_aes_encrypt(plaintext)
            self.password = f'${ALGO_AES}${ciphertext}'
