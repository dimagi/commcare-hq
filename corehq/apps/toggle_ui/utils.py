from couchexport.writers import Excel2007ExportWriter
from django.utils.translation import ugettext as _
from io import BytesIO
from corehq.toggles import all_toggles


def find_static_toggle(slug):
    for toggle in all_toggles():
        if toggle.slug == slug:
            return toggle


def get_flags_with_tag(tag):
    toggles_info = {}
    headers = []

    for toggle in all_toggles():
        if tag == 'all' or toggle.tag.name == tag:
            header_titles = (toggle.slug, [(
                _("label"),
                _("documention_link"),
                _("description")
            )])
            headers.append(header_titles)

            toggle_info = {
                toggle.slug: {
                    'description': toggle.description or '',
                    'documention_link': toggle.help_link or '',
                    'label': toggle.label or '',
                }
            }
            toggles_info.update(toggle_info)

    return headers, toggles_info


def parse_excel_attachment_data(tag):
    (headers, tabs_info) = get_flags_with_tag(tag)

    writer = Excel2007ExportWriter()
    outfile = BytesIO()
    writer.open(header_table=headers, file=outfile)

    for tab_name, tab_info in tabs_info.items():
        first_row = [
            tab_info['description'],
            tab_info['documention_link'],
            tab_info['label']
        ]
        # data_rows = [[1, 2], [3, 4]]

        rows = [first_row]
        print(rows)
        writer.write([(tab_name, rows)])

    writer.close()
    return outfile
