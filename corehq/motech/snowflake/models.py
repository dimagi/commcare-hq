from django.db import models

from memoized import memoized

from dimagi.ext.couchdbkit import IntegerProperty

from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.models import Repeater, SQLRepeater

from .payload_generators import FormJsonCsvPayloadGenerator


class SQLSnowflakeS3Repeater(SQLRepeater):

    # `connection_settings` is used for forwarding to S3. We need
    # Snowflake credentials for triggering ingest.
    snowflake_connection_settings = models.ForeignKey(
        ConnectionSettings,
        on_delete=models.PROTECT
    )

    ...


class SnowflakeS3Repeater(Repeater):

    # `connection_settings` is used for forwarding to S3. We need
    # Snowflake credentials for triggering ingest.
    snowflake_connection_settings_id = IntegerProperty(required=True)

    payload_generator_classes = (FormJsonCsvPayloadGenerator,)

    @memoized
    def payload_doc(self, repeat_record):
        accessor = FormAccessors(repeat_record.domain)
        return accessor.get_form(repeat_record.payload_id)

    def get_url(self, repeat_record):
        return self.connection_settings.url

    # To work out the Content-MD5 header, we would need the payload
    # def get_headers(self, repeat_record):
    #     ...

    def send_request(self, repeat_record, payload):
        # Send PUT request to S3
        # https://docs.aws.amazon.com/AmazonS3/latest/API/API_PutObject.html

        # Alternatively, use Boto
        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.put_object

        try:
            directory = self.get_s3_directory()
        except S3Error:
            notify_error()
            return Response(status=500)

        # From AWS docs ...
        response = client.put_object(
            ACL='private'|'public-read'|'public-read-write'|'authenticated-read'|'aws-exec-read'|'bucket-owner-read'|'bucket-owner-full-control',
            Body=payload.encode('utf8'),
            Bucket='string',
            CacheControl='string',
            ContentDisposition='string',
            ContentEncoding='string',
            ContentLanguage='string',
            ContentLength=123,
            ContentMD5='string',
            ContentType='string',
            Expires=datetime(2015, 1, 1),
            GrantFullControl='string',
            GrantRead='string',
            GrantReadACP='string',
            GrantWriteACP='string',
            Key='string',
            Metadata={
                'string': 'string'
            },
            ServerSideEncryption='AES256'|'aws:kms',
            StorageClass='STANDARD'|'REDUCED_REDUNDANCY'|'STANDARD_IA'|'ONEZONE_IA'|'INTELLIGENT_TIERING'|'GLACIER'|'DEEP_ARCHIVE'|'OUTPOSTS',
            WebsiteRedirectLocation='string',
            SSECustomerAlgorithm='string',
            SSECustomerKey='string',
            SSEKMSKeyId='string',
            SSEKMSEncryptionContext='string',
            BucketKeyEnabled=True|False,
            RequestPayer='requester',
            Tagging='string',
            ObjectLockMode='GOVERNANCE'|'COMPLIANCE',
            ObjectLockRetainUntilDate=datetime(2015, 1, 1),
            ObjectLockLegalHoldStatus='ON'|'OFF',
            ExpectedBucketOwner='string'
        )

        url = self.get_url(repeat_record)
        return requests.put(
            self.domain, url, payload,
            headers=self.get_headers(repeat_record),
            auth_manager=self.connection_settings.get_auth_manager(),
            verify=self.verify,
            notify_addresses=self.connection_settings.notify_addresses,
            payload_id=repeat_record.payload_id,
        )

    def get_s3_directory(self):
        """
        Return the directory in which to put CSV files
        """
        directory = get_last_directory()
        if not directory:
            directory = create_directory()

        # Don't do this. Just use a monthly scheduled task to manage
        # ingests and directories.
        # elif older_than(directory, days=60):
        #     trigger_ingest()  # Raises S3Error or SnowflakeError
        #     delete_directory(directory)
        #     directory = create_directory()
        #
        # elif older_than(directory, days=30):
        #     try:
        #         trigger_ingest()
        #     except (S3Error, SnowflakeError):
        #         pass  # Just keep using this directory for now
        #     else:
        #         delete_directory(directory)
        #         directory = create_directory()

        return directory
