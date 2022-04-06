from copy import copy
from datetime import datetime
from difflib import unified_diff
from tempfile import NamedTemporaryFile

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from corehq.elastic import get_es_new
from corehq.pillows.mappings import CANONICAL_NAME_INFO_MAP


class Command(BaseCommand):
    help = "Update an existing ES mapping. If there are conflicting changes this command will fail."

    def add_arguments(self, parser):
        parser.add_argument(
            'index_name',
            help='INDEX NAME or ALIAS',
        )
        parser.add_argument(
            '--noinput',
            action='store_true',
            dest='noinput',
            default=False,
            help='Skip important confirmation warnings.'
        )
        parser.add_argument(
            '-n', '--dry-run',
            action='store_true',
            default=False,
            help='Perform a dry-run (do not update the mapping). Useful for '
                 'viewing expected mapping changes (diff).',
        )
        parser.add_argument(
            '--no-diff',
            action='store_true',
            default=False,
            help='Print the before/after diff.'
        )
        parser.add_argument(
            '-q', '--quiet',
            action='store_true',
            default=False,
            help='Suppress all non-error output (implies --no-diff).'
        )

    def handle(self, index_name, dry_run, no_diff, quiet, **options):
        noinput = options.pop('noinput')
        for cname, index_info in CANONICAL_NAME_INFO_MAP.items():
            if index_name == index_info.alias or index_name == index_info.index:
                break
        else:
            raise CommandError(f"No matching index found: {index_name}")

        msg = f"Confirm that you want to update the mapping for {index_info.index!r} [y/N]: "
        if not noinput and input(msg).lower() != "y":
            raise CommandError("abort")

        if quiet:
            def noop(*args, **kw):
                pass
            self.stdout.write = noop
            no_diff = True

        if not no_diff:
            before = self.get_mapping_text_lines(cname)
        if dry_run:
            self.stdout.write("[DRY-RUN] mapping not updated")
        else:
            self.update_mapping(index_info)
            self.stdout.write("Index successfully updated")

        if not no_diff:
            after = self.get_mapping_text_lines(cname, not dry_run)
            for line in unified_diff(before, after, "before.py", "after.py"):
                if line.startswith("-") and not line.startswith("--- "):
                    style_func = self.style.ERROR  # color red
                elif line.startswith("+") and not line.startswith("+++ "):
                    style_func = self.style.SUCCESS  # color green
                else:
                    style_func = None
                self.stdout.write(line, style_func, ending="")

    def update_mapping(self, index_info):
        es = get_es_new()
        mapping = copy(index_info.mapping)
        mapping["_meta"]["created"] = datetime.utcnow().isoformat()
        mapping_res = es.indices.put_mapping(
            index_info.type,
            {index_info.type: mapping},
            index_info.index,
        )
        if not mapping_res.get("acknowledged", False):
            self.stderr.write(mapping_res)
            raise CommandError("Mapping update failed")

    def get_mapping_text_lines(self, cname, from_elastic=True):
        with NamedTemporaryFile("w+") as file:
            argv = ["print_elastic_mappings", "-o", file.name, cname]
            if from_elastic:
                argv.append("--from-elastic")
            try:
                call_command(*argv)
            except CommandError as exc:
                self.stderr.write(
                    f"failed to fetch mapping for diff ({exc!s})",
                    self.style.WARNING,
                )
                return []
            file.seek(0)
            return list(file)
