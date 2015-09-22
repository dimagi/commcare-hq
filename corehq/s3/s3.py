from django.conf import settings
from dimagi.utils.decorators.memoized import memoized

import boto3
from botocore.utils import fix_s3_host


class ObjectStore(object):

    def __init__(self, domain=None):
        self.domain = domain
        self.resource = boto3.resource(
            's3',
            use_ssl=settings.RIAKCS_SSL,
            endpoint_url='http://{}:{}'.format(settings.RIAKCS_HOST, settings.RIAKCS_PORT),
            aws_access_key_id=settings.RIAKCS_KEY,
            aws_secret_access_key=settings.RIAKCS_SECRET,
        )

        # boto3 automatically overwrites the endpoint url: https://github.com/boto/boto3/issues/259
        self.resource.meta.client.meta.events.unregister('before-sign.s3', fix_s3_host)
        self.bucket = self._init_bucket()

    @property
    def bucket_name(self):
        return self.domain or settings.RIAKCS_DEFAULT_BUCKET

    @property
    @memoized
    def _init_bucket(self):
        try:
            bucket = self.resource.Bucket(self.bucket_name)
        except botocore.exceptions.ClientError:
            error_code = int(e.response['Error']['Code'])
            if error_code == 404:
                bucket = self.conn.create_bucket(self.bucket_name)
            else:
                raise

        return bucket

    def set(key, value, content_length=None):
        return boto3.s3.Object(self.bucket_name, key).put(
            Body=value,
            ContentLength=content_length,
        )

    def get(key):
        return boto3.s3.Object(self.bucket_name, key).get()
