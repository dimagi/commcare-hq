import logging
import os
import re

from django.core.management import BaseCommand, CommandError


logger = logging.getLogger('hqdefine_to_esm')

IMPORT_PATTERN = r'\s*["\']([^,]*)["\'],$'
ARGUMENT_PATTERN = r'\s*([^,]*),?$'


class Command(BaseCommand):
    help = '''
        Attempts to migrate a JavaScript file from hqDefine to ESM syntax.
        Expects input file to be formatted with hqDefine on one line,
        then one line per import, then one line per hqDefine argument.

        Also attempts to remove "use strict" directive, because modules automatically use strict.
    '''
    dedent = 4

    def add_arguments(self, parser):
        parser.add_argument('filename', help='File to migrate')

    def handle(self, filename, **options):
        if not os.path.exists(filename):
            raise CommandError(f"Could not find {filename}")

        with open(filename, 'r') as fin:
            lines = fin.readlines()

        # Parse imports
        self._init_parser()
        imports = []
        arguments = []
        line_index = 0
        while self.in_hqdefine_block:
            if line_index >= len(lines):
                self._fail_parsing()

            line = lines[line_index]
            line_index += 1

            if self._update_parser_location(line):
                continue
            if self.in_imports:
                imports.append(self._parse_import(line))
            elif self.in_arguments:
                arguments.append(self._parse_argument(line))

        # Rewrite file
        with open(filename, 'w') as fout:
            # Move commcarehq to the top
            if "commcarehq" in imports:
                fout.write('import "commcarehq";\n')

            # Add imports, ESM-style
            for index, dependency in enumerate(imports):
                if dependency is None or dependency == "commcarehq":
                    continue

                if index < len(arguments):
                    out = f'import {arguments[index]} from "{dependency}";\n'
                else:
                    out = f'import "{dependency}";\n'

                fout.write(out)
            fout.write("\n")

            # Write remaining file
            for line in lines[line_index:]:
                if self._is_use_strict(line) or self._is_hqdefine_close(line):
                    continue

                fout.write(self._dedent(line))

        logger.info(f"Rewrote {filename}")

    def _is_use_strict(self, line):
        return 'use strict' in line

    def _is_hqdefine_open(self, line):
        return 'hqDefine' in line

    def _is_hqdefine_close(self, line):
        return line.startswith("});")

    def _parse_import(self, line):
        return self._parse_item(IMPORT_PATTERN, line, "import")

    def _parse_argument(self, line):
        return self._parse_item(ARGUMENT_PATTERN, line, "argument")

    def _parse_item(self, pattern, line, description=""):
        match = re.search(pattern, line)
        if match:
            item = match.group(1)
            logger.info(f"Found {description}: {item}")
            if item.endswith("\n"):
                item = item[:-1]
            return item
        logger.warning(f"Could not parse {description} from line: {line}")

    def _init_parser(self):
        self.in_hqdefine_block = True
        self.in_imports = False
        self.in_arguments = False

    def _fail_parsing(self):
        if self.in_arguments:
            status = "in arguments block"
        elif self.in_imports:
            status = "in imports block"
        else:
            status = "before imports block"
        raise CommandError(f"Could not parse file. Ran out of code {status}.")

    def _update_parser_location(self, line):
        if self._is_use_strict(line):
            return True
        if self._is_hqdefine_open(line):
            self.in_imports = True
            return True
        if self.in_imports and 'function' in line:
            self.in_imports = False
            self.in_arguments = True
            return True
        if self.in_arguments and ')' in line:
            self.in_arguments = False
            self.in_hqdefine_block = False
            return True
        return False

    def _dedent(self, line):
        if line.startswith(" " * self.dedent):
            line = line[self.dedent:]
        return line
