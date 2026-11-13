# Chat Widget Translation Integration

This document explains how CommCare HQ integrates with the Open Chat Studio widget's internationalization (i18n) features.

## Overview

As of version 0.5.0, the open-chat-studio-widget supports overriding UI translations via JSON files. This integration hooks into Django's existing translation framework to generate widget-compatible translation files.

## Architecture

The integration consists of three main components:

### 1. Management Command

**File:** `corehq/apps/hqwebapp/management/commands/generate_widget_translations.py`

This command generates JSON translation files for each language configured in Django settings.

**Usage:**
```bash
python manage.py generate_widget_translations
```

**Options:**
- `--output-dir`: Specify a custom output directory (default: `STATIC_ROOT/ocs-widget`)

### 2. Template Integration

**File:** `corehq/apps/hqwebapp/templates/hqwebapp/base.html`

The widget element now includes:
- `language="{{ LANGUAGE_CODE }}"` - Sets the widget's UI language
- `translations-url="{% static 'ocs-widget/' %}{{ LANGUAGE_CODE }}.json"` - Points to the generated translation file

### 3. Translation Strings

All widget UI strings are defined in the management command using Django's `gettext` (`_()`) function. This means they:
- Are extracted by `makemessages` along with other Django translations
- Can be translated using the standard Django translation workflow
- Are compiled into the widget JSON files by the `generate_widget_translations` command

## References

- [Open Chat Studio Widget Documentation](https://docs.openchatstudio.com/chat_widget/reference/#internationalization)
