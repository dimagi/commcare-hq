import functools
import gzip
import json
import os
import tempfile
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

import boto3
from botocore.exceptions import ClientError
from s3transfer import S3Transfer

from corehq.apps.es import CaseES, FormES
from corehq.blobs.s3db import is_not_found
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    """Created for the data mining project: https://github.com/dimagi/dimagi_defaulters
    """
    help = "Dump a raw JSON data to disk and upload to S3."

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('-r', '--s3-region', dest='region', default='us-east-1')
        parser.add_argument('-k', '--s3-key', dest='key')
        parser.add_argument('-s', '--s3-secret', dest='secret')
        parser.add_argument('-b', '--s3-bucket', dest='bucket')
        parser.add_argument('-t', '--type', choices=['forms', 'cases'], dest='type')

    def handle(self, domain, **options):
        self.domain = domain
        self.timestamp = datetime.utcnow()

        if options['key']:
            s3_key = options['key']
            s3_secret = options['secret']
        else:
            s3_key = settings.S3_ACCESS_KEY
            s3_secret = settings.S3_SECRET_KEY

        self.bucket = options['bucket'] or 'raw-data-{}'.format(domain)
        self.client = boto3.client(
            's3',
            region_name=options['region'],
            aws_access_key_id=s3_key,
            aws_secret_access_key=s3_secret
        )
        self._create_bucket()

        exporters = list({
            'forms': _get_form_query,
            'cases': functools.partial(_get_query, CaseES),
        }.items())

        if options['type']:
            exporters = [exp for exp in exporters if exp[0] == options['type']]

        for type_, query_fn in exporters:
            query = query_fn(domain)
            path = _dump_docs(query, type_)
            self._upload(type_, path)
            os.remove(path)

    def _create_bucket(self):
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError as err:
            if not is_not_found(err):
                raise
            self.client.create_bucket(Bucket=self.bucket)

    def _upload(self, type_, path):
        filename = _filename(self.domain, type_, self.timestamp)
        print("Uploading {} to s3://{}/{}".format(type_, self.bucket, filename))
        S3Transfer(self.client).upload_file(
            path, self.bucket, filename,
            extra_args={'ServerSideEncryption': 'AES256'}
        )


def _dump_docs(query, type_):
    print("Dumping {}".format(type_))

    total_docs = query.count()
    path, file = _get_file(type_)
    with file:
        for doc in with_progress_bar(query.size(500).scroll(), length=total_docs):
            file.write('{}\n'.format(json.dumps(doc)))
    return path


def _filename(domain, type_, date):
    return 'raw_{}_dump_{}_{}.jsonl.gz'.format(
        type_,
        domain,
        date.strftime('%Y%m%d_%H%M%S')
    )


def _get_file(doc_type):
    with tempfile.NamedTemporaryFile(prefix='domain_dump_raw_{}_'.format(doc_type),
            mode='wb', delete=False) as fileobj:
        zipped_obj = gzip.GzipFile(filename=fileobj.name, mode='wb')
    return zipped_obj.name, zipped_obj


def _get_form_query(domain):
    return (FormES(for_export=True)
            .domain(domain)
            .remove_default_filter('has_user'))


def _get_query(ES, domain):
    return ES(for_export=True).domain(domain)
