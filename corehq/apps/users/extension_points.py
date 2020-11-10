from corehq.extensions import extension_point, ResultFormat


def update_audio_path_if_required(current_row, old_row, langs):
    for mutator in translations_audio_path_updater():
        mutator(current_row, old_row, langs)


@extension_point(result_format=ResultFormat.FLATTEN)
def translations_audio_path_updater():
    """Checks if translation text has been updated, if it is then
    the funtion will update the audio path in the translation dict.
    If both audio path and text have been updated then the function will
    raise a ValueError.
    Returns:
        A list of functions that will be called to update the audio path. The functions
        must take the following arguments and return the mutated query:
        * current_row: Dict containing values of uploaded row of translations
        * old_row: Dict containing values of older row of transaltions
        * langs: An array of language ids
    """


@extension_point(result_format=ResultFormat.FLATTEN)
def get_older_translation_rows():
    """Returns an array of rows of older translations that are present in app
    must take the following arguments
    * app
    * lang
    * sheet_name
    * is_single_sheet
    """


def extract_older_rows(app, lang, sheet_name, is_single_sheet):
    older_rows = None
    for fn in get_older_translation_rows():
        older_rows = fn(app, lang, sheet_name, is_single_sheet)
    return older_rows
