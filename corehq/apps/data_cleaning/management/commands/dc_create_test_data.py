import uuid

from django.core.management.base import BaseCommand

from corehq.apps.data_cleaning.management.commands.utils import input_validation
from corehq.apps.data_cleaning.management.commands.utils.fake_data_users import (
    DATA_CLEANING_TEST_USER_PREFIX,
)
from corehq.apps.data_cleaning.management.commands.utils.fake_plant_data import (
    get_plant_case_data_with_issues,
)
from corehq.apps.receiverwrapper.auth import AuthContext
from corehq.apps.users.dbaccessors import get_all_commcare_users_by_domain
from corehq.apps.users.models import WebUser
from corehq.form_processor.submission_post import SubmissionPost
from corehq.form_processor.utils import convert_xform_to_json
from corehq.util.timer import TimingContext


class Command(BaseCommand):
    help = (
        f'Generates test data for the Case Data Cleaning based '
        f"on the '{input_validation.DATA_CLEANING_TEST_APP_NAME}' app structure."
    )

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('submitting_web_user')
        parser.add_argument('num_submissions', type=int)

    def handle(self, domain, submitting_web_user, num_submissions, **options):
        is_real_domain = input_validation.is_real_domain(domain)
        if not is_real_domain:
            self.stderr.write(input_validation.get_domain_missing_error(domain))
            return
        fake_app = input_validation.get_fake_app(domain)
        if not fake_app:
            self.stderr.write(
                f"Domain {domain} does not have the '{input_validation.DATA_CLEANING_TEST_APP_NAME}' app."
            )
            self.stdout.write('Please run the data_cleaning_add_fake_data_app command first.')
            return
        web_user = WebUser.get_by_username(submitting_web_user)
        if not web_user:
            self.stderr.write(f'Web user {submitting_web_user} does not exist.')
            return

        data_cleaning_fake_users = [
            u
            for u in get_all_commcare_users_by_domain(domain)
            if u.username.startswith(DATA_CLEANING_TEST_USER_PREFIX)
        ]
        if not data_cleaning_fake_users:
            self.stderr.write(f'No fake users found for domain {domain}.')
            self.stdout.write('Please run the data_cleaning_create_users_for_fake_data command first.')
            return
        for num in range(num_submissions):
            self.stdout.write(f'\n\nSubmitting {num + 1} of {num_submissions}...')
            self.create_fake_data(domain, web_user, data_cleaning_fake_users, fake_app)

    def create_fake_data(self, domain, web_user, data_cleaning_fake_users, fake_app):
        fake_data = get_plant_case_data_with_issues(data_cleaning_fake_users)
        instance = bytes(self.get_form_data(fake_data), 'utf-8')
        instance_json = convert_xform_to_json(instance)

        with TimingContext() as timer:
            submission_post = SubmissionPost(
                instance=instance,
                instance_json=instance_json,
                attachments={},
                domain=domain,
                app_id=fake_app.get_id,
                build_id=fake_app.get_id,
                auth_context=AuthContext(
                    domain=domain,
                    user_id=web_user.get_id,
                    authenticated=True,
                ),
                location='http://localhost:8000',
                received_on=None,
                date_header=None,
                path=f'/a/{domain}/receiver/secure/{fake_app.get_id}/',
                submit_ip='127.0.0.1',
                last_sync_token=uuid.uuid1(),
                openrosa_headers={'HTTP_X_OPENROSA_VERSION': '3.0'},
                force_logs=False,
                timing_context=timer,
            )
            result = submission_post.run()
        self.stdout.write(f'Form Submitted with result: {result}\n')

    def get_case_data(self, fake_data):
        case_data = [
            '<n0:case case_id="{case_id}" '
            'date_modified="{time_end}" user_id="{user_id}" xmlns:n0="http://commcarehq.org/case/transaction/v2">',
            '<n0:create>',
            '<n0:case_name>{plant_name}</n0:case_name>',
            '<n0:owner_id>{user_id}</n0:owner_id>',
            '<n0:case_type>plant</n0:case_type>',
            '</n0:create>',
            '<n0:update>',
        ]
        case_update_data = []
        if fake_data['description'] is not None:
            case_update_data.append('<n0:description>{description}</n0:description>')
        if fake_data['health_indicators'] is not None:
            case_update_data.append('<n0:health_indicators>{health_indicators}</n0:health_indicators>')
        if fake_data['height_cm'] is not None:
            case_update_data.append('<n0:height_cm>{height_cm}</n0:height_cm>')
        if fake_data['height'] is not None:
            case_update_data.append('<n0:height>{height}</n0:height>')
        if fake_data['last_repotted'] is not None:
            case_update_data.append('<n0:last_repotted>{last_repotted}</n0:last_repotted>')
        if fake_data['last_watered_datetime'] is not None:
            case_update_data.append('<n0:last_watered_datetime>{last_watered_datetime}</n0:last_watered_datetime>')
        if fake_data['last_watered_on'] is not None:
            case_update_data.append('<n0:last_watered_on>{last_watered_on}</n0:last_watered_on>')
        if fake_data['last_watered_time'] is not None:
            case_update_data.append('<n0:last_watered_time>{last_watered_time}</n0:last_watered_time>')
        if fake_data['nickname'] is not None:
            case_update_data.append('<n0:nickname>{nickname}</n0:nickname>')
        if fake_data['num_leaves'] is not None:
            case_update_data.append('<n0:number_of_leaves>{num_leaves}</n0:number_of_leaves>')
        if fake_data['pot_type'] is not None:
            case_update_data.append('<n0:pot_type>{pot_type}</n0:pot_type>')
        case_data.extend(case_update_data)
        case_data.extend(
            [
                '</n0:update>',
                '</n0:case>',
            ]
        )
        return case_data

    def get_form_data(self, fake_data):
        form_data = [
            "<?xml version='1.0' ?>"
            '<data uiVersion="1" version="38" '
            'name="Add Plant" xmlns:jrm="http://dev.commcarehq.org/jr/xforms" '
            'xmlns="http://openrosa.org/formdesigner/B55100FC-10F5-4CED-BD8D-C9B7B6637E93">',
            '<plant_name>{plant_name}</plant_name>',
        ]
        if fake_data['nickname'] is not None:
            form_data.append('<nickname>{nickname}</nickname>')
        if fake_data['description']:
            form_data.append('<description>{description}</description>')
        if fake_data['height_cm'] is not None:
            form_data.append('<height_cm>{height_cm}</height_cm>')
        if fake_data['height'] is not None:
            form_data.append('<height>{height}</height>')
        if fake_data['num_leaves'] is not None:
            form_data.append('<number_of_leaves>{num_leaves}</number_of_leaves>')
        if fake_data['last_watered_on'] is not None:
            form_data.append('<last_watered_on>{last_watered_on}</last_watered_on>')
        if fake_data['last_watered_time'] is not None:
            form_data.append('<last_watered_time>{last_watered_time}</last_watered_time>')
        if fake_data['last_watered_datetime'] is not None:
            form_data.append('<last_watered_datetime>{last_watered_datetime}</last_watered_datetime>')
        if fake_data['last_repotted'] is not None:
            form_data.append('<last_repotted>{last_repotted}</last_repotted>')
        if fake_data['health_indicators'] is not None:
            form_data.append('<health_indicators>{health_indicators}</health_indicators>')
        if fake_data['pot_type'] is not None:
            form_data.append('<pot_type>{pot_type}</pot_type>')
        form_data.extend(self.get_case_data(fake_data))
        form_data.extend(
            [
                '<n1:meta xmlns:n1="http://openrosa.org/jr/xforms">',
                '<n1:deviceID>Management Command</n1:deviceID>',
                '<n1:timeStart>{time_start}</n1:timeStart>',
                '<n1:timeEnd>{time_end}</n1:timeEnd>',
                '<n1:username>{username}</n1:username>',
                '<n1:userID>{user_id}</n1:userID>',
                '<n1:instanceID>{form_id}</n1:instanceID>',
                '<n2:appVersion xmlns:n2="http://commcarehq.org/xforms">Management Command: 1.0</n2:appVersion>',
                '<n1:drift>0</n1:drift>',
                '</n1:meta>',
                '</data>',
            ]
        )
        return ''.join(form_data).format(**fake_data)
