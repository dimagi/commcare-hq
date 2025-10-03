import json
import re
import uuid
from copy import deepcopy

from django.core.management import BaseCommand, CommandError

from corehq.apps.app_manager.const import MOBILE_UCR_VERSION_2
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.exceptions import AppValidationError
from corehq.apps.app_manager.tasks import prune_auto_generated_builds
from corehq.toggles import MOBILE_UCR

# Mobile UCR report references:
# V1: `instance('reports')/reports/report[@id='xxxxxxx']`
# V2: `instance('commcare-reports:xxxxxxx')`
V1_REPORT_REFS = r"instance\('reports'\)/reports/report\[@id='([^']+)'\]"
V2_REPORT_REFS = r"instance\('commcare-reports:\1'\)"

# Mobile UCR column references:
# V1: `column[@id = 'column_id']`
# V2: `column_id`
V1_COLUMN_REFS = r"column\[@id.?=.?'([^']+)'\]"
V2_COLUMN_REFS = r'\1'


class Command(BaseCommand):
    help = 'Convert Mobile UCR references from V1 to V2'

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('app_id')

    def handle(self, domain, app_id, **options):
        # Based on ApplicationBase.make_build()
        if not MOBILE_UCR.enabled(domain):
            raise CommandError(
                'MOBILE_UCR is not enabled for "%s"' % domain,
                returncode=1
            )

        v1_app = get_app(domain, app_id)
        assert v1_app.copy_of is None

        if v1_app.mobile_ucr_restore_version != MOBILE_UCR_VERSION_2:
            raise CommandError(
                'The Mobile UCR version of "%s" must be set to 2' % v1_app.name,
                returncode=2
            )

        app_dict = _copy_app_dict(v1_app.to_json())
        app_dict = _replace_v1_refs(app_dict)
        v2_app = v1_app.__class__.wrap(app_dict)
        v2_app.convert_app_to_build(
            v1_app._id,
            user_id=None,
            comment=self.help,
        )
        v2_app.copy_attachments(v1_app)
        assert not v2_app._id  # _copy_app_dict() dropped _id
        v2_app._id = uuid.uuid4().hex
        errors = v2_app.validate_app()
        if errors:
            raise AppValidationError(errors)
        if v2_app.create_build_files_on_build:
            v2_app.create_build_files()
        prune_auto_generated_builds.delay(v1_app.domain, v1_app._id)
        v2_app.save(increment_version=False)

        self.stdout.write(self.style.SUCCESS(
            'Successfully converted app "%s"' % v1_app.name
        ))


def _copy_app_dict(app_dict):
    bad_keys = (
        '_id',
        '_rev',
        '_attachments',
        'external_blobs',
        'short_odk_url',
        'short_odk_media_url',
        'recipients'
    )
    return {k: deepcopy(v) for k, v in app_dict.items() if k not in bad_keys}


def _replace_v1_refs(app_dict):
    app_str = json.dumps(app_dict)
    app_str = re.sub(V1_REPORT_REFS, V2_REPORT_REFS, app_str)
    app_str = re.sub(V1_COLUMN_REFS, V2_COLUMN_REFS, app_str)
    return json.loads(app_str)
