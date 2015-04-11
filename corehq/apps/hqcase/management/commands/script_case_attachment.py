from datetime import datetime, timedelta
from getpass import getpass
from optparse import make_option
import os
import uuid
from django.contrib.auth.models import User
from django.core.management.base import NoArgsCommand, BaseCommand
import sys
from casexml.apps.case.models import CommCareCase
from corehq.apps.users.models import CommCareUser
from corehq.util.dates import datetime_to_iso_string
from dimagi.utils.post import post_data


XFORM_TEMPLATE = """<?xml version='1.0' ?>
    <data uiVersion="1" version="1" name="Scripted Attachment Updates"
        xmlns:jrm="http://dev.commcarehq.org/jr/xforms"
        xmlns:cc="http://commcarehq.org/xforms"
        xmlns="http://dev.commcarehq.org/test/case_multimedia_scripted">
    <n0:case case_id="%(case_id)s" user_id="%(user_id)s" date_modified="%(date_modified)s"
        xmlns:n0="http://commcarehq.org/case/transaction/v2">
        <n0:attachment>
            %(attachments)s
        </n0:attachment>
    </n0:case>
    <n1:meta xmlns:n1="http://openrosa.org/jr/xforms">
        <n1:deviceID>script_case_attachment</n1:deviceID>
        <n1:timeStart>%(time_start)s</n1:timeStart>
        <n1:timeEnd>%(time_end)s</n1:timeEnd>
        <n1:username>%(username)s</n1:username>
        <n1:userID>%(user_id)s</n1:userID>
        <n1:instanceID>%(doc_id)s</n1:instanceID>
    </n1:meta>
    </data>"""

#http://stackoverflow.com/questions/392041/python-optparse-list
def parse_files(option, opt, value, parser):
    pairs = value.split(',')
    stream_dict = {}
    for p in pairs:
        s = p.split('=')
        if len(s) != 2:
            print "argument error, %s should be key=filepath" % s
            sys.exit()
        attach_key = s[0]
        attach_file = s[1]
        file_exists = os.path.exists(attach_file)
        print "\tattach %s: %s=>%s" % (attach_key, attach_file, file_exists)
        stream_dict[attach_key] = attach_file
    setattr(parser.values, option.dest, stream_dict)


def parse_list(option, opt, value, parser):
    setattr(parser.values, option.dest, value.split(','))


class Command(BaseCommand):
    help = "A shortcut script to generate xform submissions that legally put attachments on your case"
    option_list = NoArgsCommand.option_list + (
        make_option('--remove',
                    type="string",
                    action='callback',
                    dest="remove",
                    callback=parse_list,
                    default="",
                    help='Remove attachment(s) by name: name1,name2,name3'),
        make_option('--files',
                    type="string",
                    action='callback',
                    callback=parse_files,
                    dest='files',
                    default={},
                    help='files to upload file1=path1,file2=path2,file3=path3'),
        make_option('--case',
                    action='store',
                    dest='case',
                    default=None,
                    help='case_id to update'),
        make_option('--username',
                    action='store',
                    dest='username',
                    default=None,
                    help='username performing this action'),
        make_option('--password',
                    action='store',
                    dest='password',
                    default=None,
                    help='password of user performing this action'),
        make_option('--url',
                    action='store',
                    dest='url',
                    default="http://localhost:8000",
                    help='URL to submit to'),
    )

    def get_credentials(self):
        if self.username is None:
            self.username = raw_input("""\tEnter username: """)
            if self.username is None or self.username == "":
                print "\tYou need to enter a username"
                sys.exit()

        if self.password is None:
            self.password = getpass("""\tEnter %s's password: """ % self.username)
            if self.password is None or self.password == "":
                print "\tNo password found"
        try:
            user = User.objects.get(username=self.username)
            return user.check_password(self.password)
        except ValueError, ex:
            print "\tError, user doesn't exist, aborting"
            sys.exit()


    def handle(self, *args, **options):
        print "Options:"
        print options
        self.username = options['username']
        self.password = options['password']
        self.url_base = options['url']
        self.case_id = options['case']

        if self.case_id is None:
            print "\n\tNo case id, read the damn instructions"

        self.user_doc = CommCareUser.get_by_username(self.username)

        if not self.get_credentials():
            print "\n\tLogin failed, exiting"
            sys.exit()

        print "\nStarting attachment upload"

        print "here are the files"
        print options['files']

        case_doc = CommCareCase.get(self.case_id)
        domain = case_doc.domain
        submit_id = uuid.uuid4().hex

        def attach_block(key, filename):
            return '<n0:%s src="%s" from="local"/>' % (key, os.path.split(filename)[-1])
        attachments = [attach_block(k, v) for k, v in options['files'].items()]
        format_dict = {
            "time_start": datetime_to_iso_string(datetime.utcnow() - timedelta(seconds=5)),
            "time_end": datetime_to_iso_string(datetime.utcnow()),
            "date_modified": datetime_to_iso_string(datetime.utcnow()),
            "user_id": self.user_doc.get_id,
            "username": self.username,
            "doc_id": submit_id,
            "case_id": self.case_id,
            "attachments": ''.join(attachments)
        }
        url = self.url_base + "/a/%s/receiver" % domain

        attachment_tuples = [(k, v) for k, v in options['files'].items()]

        final_xml = XFORM_TEMPLATE % format_dict
        print post_data(final_xml, url, path=None, use_curl=True, use_chunked=True, is_odk=True, attachments=attachment_tuples)






