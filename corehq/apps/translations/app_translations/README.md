Bulk Application Translations
-----------------------------

HQ supports a file download and re-upload to update all application-specific translations.

The download has two variants, a multi-sheet and a single-sheet format. Both are tolerant of partial uploads:
missing sheets, missing language columns (as opposed to the columns needed to identify a row), and missing rows
(with some exceptions for module translations, which depend on case properties being present and correctly ordered).

The default multi-sheet format contains a first "menus and forms" sheet for editing module and form names and menu media. It then contains a sheet for each module and each form.

The single-sheet format allows editing all of the same content, just with all rows in the same sheet. Depending on the type of row (module/form name, module content, or form content) certain columns will be blank.

The UI defaults to the multi-sheet download. There's a feature flagged ability to select a single language, which downloads the single sheet format for that language. There's no technical reason that the single sheet download is also a single language download.

For domains with Transifex integration, Transifex generates Excel files in the multi-sheet format that HQ accepts.

Code is organized into
- `download.py` Generation of Excel downloads
- `upload_app.py` Entry point to upload code
- `upload_module.py` Helper functions to update module content
- `upload_form.py` Helper functions to update form content
- `utils.py` Helper functions shared by download and upload, such as header generators
