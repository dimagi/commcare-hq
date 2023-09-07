from django.core.management import BaseCommand

from corehq.apps.app_manager.management.commands.helpers import get_all_app_ids
from corehq.apps.app_manager.models import Application
from corehq.blobs import get_blob_db
from corehq.blobs.mixin import BlobMetaRef


class Command(BaseCommand):
    help = """
    Repair apps with broken form blob references by reverting those
    references to a previous version of the form.
    """

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            '-a', '--app',
            nargs='*',
            dest='app_ids',
            help='App ID with broken blob(s).',
        )
        parser.add_argument(
            '--write',
            action='store_true',
            default=False,
            help="Write changes. Only report changes that would be made if this option is not specified.",
        )

    def handle(self, domain, app_ids, write, **options):
        assert domain is not None, "domain is required"
        if not app_ids:
            app_ids = self.get_app_ids(domain)
        for app_id in app_ids:
            app = Application.get(app_id)
            if app.domain != domain:
                print(f"Ignoring app ({app._id}) in wrong domain: {app.domain}")
                continue
            self.fix_app_blobs(app, write)
        if not write:
            print("\nTHIS WAS A DRY RUN. Broken apps were not fixed.")

    def get_app_ids(self, domain):
        return list(get_all_app_ids(domain=domain, include_builds=False))

    def fix_app_blobs(self, app, write):
        db = get_blob_db()
        metas_by_key = {m.key: m for m in db.metadb.get_for_parent(app._id)}
        broken = {}
        for name, ref in app.blobs.items():
            found = metas_by_key.pop(ref.key, None)
            if not found:
                form_name = get_form_name(app, name)
                if form_name is None:
                    blob_type = ""
                    form_name = ""
                else:
                    blob_type = "form "
                    form_name = f" - {form_name}"
                print(f"Found broken {blob_type}blob ref: {name}{form_name}")
                broken[name] = ref

        orphan_metas = {m.name: m for m in metas_by_key.values()}
        updated = False
        for name, broke in broken.items():
            meta = orphan_metas.get(name)
            if meta is None:
                raise NotImplementedError("TODO")
            assert meta.key != broke.key, (broke, meta)
            print(f"Replacing {name}: {broke} with {meta} (content_length={meta.content_length})")
            if write:
                app.blobs[name] = BlobMetaRef(
                    key=meta.key,
                    blobmeta_id=meta.id,
                    content_length=meta.content_length,
                    content_type=meta.content_type,
                )
                updated = True

        if updated and write:
            app.save()


def get_form_name(app, blob_name):
    for module in app.modules:
        for form in module.forms:
            filename = f"{form.get_unique_id()}.xml"
            if filename == blob_name:
                return form.name
    return None
