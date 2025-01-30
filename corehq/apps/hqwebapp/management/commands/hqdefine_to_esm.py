import logging
import os
import re

from django.core.management import BaseCommand, CommandError


logger = logging.getLogger('hqdefine_to_esm')

IMPORT_PATTERN = r'\s*["\']([^,]*)["\'],?$'
ARGUMENT_PATTERN = r'\s*([^,]*),?$'


class Command(BaseCommand):
    help = '''
        Attempts to migrate a JavaScript file from hqDefine to ESM syntax.
        Expects input file to be formatted with hqDefine on one line,
        then one line per import, then one line per hqDefine argument.

        Also attempts to remove "use strict" directive, because modules automatically use strict.
    '''
    dedent_size = 4

    def add_arguments(self, parser):
        parser.add_argument('filename', help='File to migrate')

    def handle(self, filename, **options):
        if not os.path.exists(filename):
            raise CommandError(f"Could not find {filename}")

        with open(filename, 'r') as fin:
            lines = fin.readlines()

        # Parse imports
        self.init_parser()
        imports = []
        arguments = []
        line_index = 0
        while self.in_hqdefine_block:
            if line_index >= len(lines):
                self.fail_parsing()

            line = lines[line_index]
            line_index += 1

            if self.update_parser_location(line):
                if self.in_arguments:
                    arguments.extend(self.parse_one_line_arguments(line))
                continue
            if self.in_imports:
                imports.append(self.parse_import(line))
            elif self.in_arguments:
                arguments.append(self.parse_argument(line))

        # Rewrite file
        with open(filename, 'w') as fout:
            # Move commcarehq to the top
            if "commcarehq" in [i[0] for i in imports]:
                fout.write('import "commcarehq";\n')

            # Add imports, ESM-style
            for index, dependency_pair in enumerate(imports):
                (dependency, comment) = dependency_pair
                if dependency is None or dependency == "commcarehq":
                    continue

                if index < len(arguments):
                    (argument, argument_comment) = arguments[index]
                    if argument_comment:
                        if comment:
                            comment = f"{comment}; {argument_comment}"
                        else:
                            comment = argument_comment
                    out = f'import {argument} from "{dependency}";'
                else:
                    out = f'import "{dependency}";'

                if comment:
                    out += '  // ' + comment

                fout.write(out + '\n')
            fout.write("\n")

            # Write remaining file
            for line in lines[line_index:]:
                if self.is_use_strict(line) or self.is_hqdefine_close(line):
                    continue

                fout.write(self.dedent(line))

        logger.info(f"Rewrote {filename}")

    def is_use_strict(self, line):
        return 'use strict' in line

    def is_hqdefine_open(self, line):
        return 'hqDefine' in line

    def is_hqdefine_close(self, line):
        return line.startswith("});")

    def parse_import(self, line):
        return self.parse_item(IMPORT_PATTERN, line, "import")

    def parse_argument(self, line):
        return self.parse_item(ARGUMENT_PATTERN, line, "argument")

    def parse_item(self, pattern, line, description=""):
        match = re.search(r'^(.*\S)\s*\/\/\s*(.*)$', line)
        if match:
            line = match.group(1)
            comment = match.group(2)
        else:
            comment = ''

        match = re.search(pattern, line)
        if match:
            item = match.group(1)
            logger.info(f"Found {description}: {item}")
            if item.endswith("\n"):
                item = item[:-1]
            return (item, comment)
        logger.warning(f"Could not parse {description} from line: {line}")

    def parse_one_line_arguments(self, line):
        match = re.search(r'function\s*\((.*)\)', line)
        if match:
            self.update_parser_location(line)
            arguments = match.group(1)
            return [arg.strip() for arg in arguments.split(',')]
        return []

    def init_parser(self):
        self.in_hqdefine_block = True
        self.in_imports = False
        self.in_arguments = False

    def fail_parsing(self):
        if self.in_arguments:
            status = "in arguments block"
        elif self.in_imports:
            status = "in imports block"
        else:
            status = "before imports block"
        raise CommandError(f"Could not parse file. Ran out of code {status}.")

    def update_parser_location(self, line):
        if self.is_use_strict(line):
            return line
        if self.is_hqdefine_open(line):
            self.in_imports = True
            return line
        if self.in_imports and 'function' in line:
            self.in_imports = False
            if re.search(r'function\s*\(\s*\)', line):
                self.in_hqdefine_block = False
            else:
                self.in_arguments = True
            return line
        if self.in_arguments and ')' in line:
            self.in_arguments = False
            self.in_hqdefine_block = False
            return line
        return False

    def dedent(self, line):
        if line.startswith(" " * self.dedent_size):
            line = line[self.dedent_size:]
        return line
