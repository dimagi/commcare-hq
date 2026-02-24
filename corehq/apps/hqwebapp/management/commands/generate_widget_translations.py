"""
Management command to generate translation JSON files for the Open Chat Studio widget.

This command generates JSON files containing translated strings for the chat widget,
hooking into Django's translation framework.

Usage:
    python manage.py generate_widget_translations
"""
import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import translation
from django.utils.translation import gettext as _


class Command(BaseCommand):
    help = "Generate translation JSON files for the Open Chat Studio widget"

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default=None,
            help='Output directory for translation files (default: STATIC_ROOT/ocs-widget)',
        )

    def handle(self, *args, **options):
        output_dir = options['output_dir']
        if not output_dir:
            output_dir = os.path.join(settings.STATIC_ROOT, 'ocs-widget')

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            self.stdout.write(self.style.SUCCESS(f'Created directory: {output_dir}'))

        # Get all available languages from Django settings
        languages = [lang[0] for lang in settings.LANGUAGES]

        for language_code in languages:
            translation.activate(language_code)

            # Generate translation dictionary with all widget strings
            translations = self._get_widget_translations()

            # Write to JSON file
            output_file = os.path.join(output_dir, f'{language_code}.json')
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(translations, f, ensure_ascii=False, indent=2)

            self.stdout.write(
                self.style.SUCCESS(f'Generated {language_code}.json ({len(translations)} keys)')
            )

        translation.deactivate()

    def _get_widget_translations(self):
        """
        Get all widget translation strings.
        These are marked for translation and will be picked up by makemessages.
        """
        return {
            # Launcher translations
            "launcher.open": _("Open chat"),

            # Window controls
            "window.close": _("Close"),
            "window.newChat": _("Start new chat"),
            "window.fullscreen": _("Enter fullscreen"),
            "window.exitFullscreen": _("Exit fullscreen"),

            # Attachment actions
            "attach.add": _("Attach files"),
            "attach.remove": _("Remove file"),
            "attach.success": _("File attached"),

            # Status messages
            "status.starting": _("Starting chat..."),
            "status.typing": _("Finding the best answer"),
            "status.uploading": _("Uploading"),

            # Modal dialogs
            "modal.newChatTitle": _("Start New Chat"),
            "modal.newChatBody": _("Starting a new chat will clear your current conversation. Continue?"),
            "modal.cancel": _("Cancel"),
            "modal.confirm": _("Confirm"),

            # Message composer
            "composer.placeholder": _("Type a message..."),
            "composer.send": _("Send message"),

            # Error messages
            "error.fileTooLarge": _("File too large"),
            "error.totalTooLarge": _("Total file size too large"),
            "error.unsupportedType": _("Unsupported file type"),
            "error.connection": _("Connection error. Please try again."),
            "error.sessionExpired": _("Session expired. Please start a new chat."),

            "branding.poweredBy": _("Powered by"),
            "branding.buttonText": _("Need Help?"),
            "branding.headerText": "",

            "content.welcomeMessages": [
                _(
                    "Hi there! I'm CommCare Companion, your personal guide to CommCare! "
                    "You can ask a question, or attach files here — like screenshots, exports, "
                    "or an App Summary — and I’ll use them to help guide you."
                )
            ],
            "content.starterQuestions": [
                _("I need help with building my CommCare application."),
                _("I need help troubleshooting my mobile application."),
                _("I need help with exporting or understanding my data.")
            ],
        }
