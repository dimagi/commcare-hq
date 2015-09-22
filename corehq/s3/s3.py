from django.conf import settings
from dimagi.utils.decorators.memoized import memoized

import boto3
from botocore.utils import fix_s3_host
from botocore.exceptions import ClientError


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

    def _init_bucket(self):
        bucket = self.resource.Bucket(self.bucket_name)
        try:
            bucket.load()
        except ClientError, e:
            error_code = int(e.response['Error']['Code'])
            if error_code == 404:
                bucket = self.resource.create_bucket(Bucket=self.bucket_name)
            else:
                raise

        return bucket

    def set(self, key, value, content_length=None):
        return self.bucket.Object(key=key).put(
            Body=value,
            ContentLength=content_length,
        )

    def get(self, key):
        return self.bucket.Object(key=key).get()
