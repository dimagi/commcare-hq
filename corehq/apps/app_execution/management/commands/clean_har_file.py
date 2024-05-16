import json
import pathlib

from django.core.management import BaseCommand

from corehq.apps.app_execution.har_parser import get_formplayer_entries


class Command(BaseCommand):
    help = """
        Filter a HAR file for entries relevant to Formplayer and remove unnecessary data.
        This is mostly used for reducing HAR file size for testing purposes.
    """

    def add_arguments(self, parser):
        parser.add_argument("har_file", type=pathlib.Path)
        parser.add_argument("-o", "--output", type=pathlib.Path,
                            help="Output file path. If not provided, will print to stdout.")

    def handle(self, har_file, output=None, *args, **options):
        with har_file.open() as f:
            har_data = json.load(f)

        formplayer_entries = get_formplayer_entries(har_data["log"]["entries"])
        cleaned_har = {
            "log": {
                "entries": [_clean_entry(entry[1]) for entry in formplayer_entries]

            }
        }
        har_dump = json.dumps(cleaned_har, indent=2)
        if output:
            with output.open("w") as f:
                f.write(har_dump)
        else:
            print(har_dump)


def _clean_entry(entry):
    request = entry["request"]
    return {
        "request": {
            "method": request["method"],
            "url": request["url"],
            "postData": {
                "text": request["postData"]["text"]
            }
        },
        "response": {
            "content": {
                "text": entry["response"]["content"]["text"]
            }
        }
    }
