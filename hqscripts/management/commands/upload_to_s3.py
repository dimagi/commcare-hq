from django.core.management.base import BaseCommand

import boto3
from botocore.exceptions import ClientError

PROFILE_LENGTH = 4  # An entry for the profile name, then each of the 3 necessary keys


class Command(BaseCommand):
    help = 'Uploads a specified file to S3'

    def add_arguments(self, parser):
        parser.add_argument('filename')
        parser.add_argument('bucket_name')
        parser.add_argument('target_name')

    def handle(self, *args, **options):
        profile = self.get_profile()

        if not self.is_valid_profile(profile):
            self.stderr.write('Error with profile configuration')
            exit(1)

        self.upload_to_s3(options['filename'], options['bucket_name'], options['target_name'], profile)

    def get_profile(self):
        profile = {}

        self.stdout.write('Paste S3 Profile: ')
        for i in range(4):
            try:
                line = input('')
            except EOFError:
                break
            if i > 0:
                key, value, = [token.strip() for token in line.split('=', 1)]
                profile[key] = value

        return profile

    def is_valid_profile(self, profile):
        keys = ['aws_access_key_id', 'aws_secret_access_key', 'aws_session_token']
        return not any(key for key in keys if key not in profile)

    def upload_to_s3(self, filename, bucket_name, target_name, profile):
        session = boto3.Session(**profile)
        s3 = session.client('s3')

        with open(filename, 'rb') as f:
            try:
                s3.upload_fileobj(f, bucket_name, target_name, ExtraArgs={})
            except ClientError as e:
                self.stderr.write('Error occurred: ', e)
                exit(1)

        self.stdout(f'{filename} uploaded successfully to S3 bucket {bucket_name} as {target_name}')
