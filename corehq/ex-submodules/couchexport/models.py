from __future__ import absolute_import
from __future__ import unicode_literals
from collections import namedtuple
from itertools import islice
from six.moves.urllib.error import URLError
from dimagi.ext.couchdbkit import Document, DictProperty,\
    DocumentSchema, StringProperty, SchemaListProperty,\
    StringListProperty, BooleanProperty
import json
from corehq.blobs.mixin import BlobMixin
from couchexport.util import SerializableFunctionProperty
from memoized import memoized
from couchdbkit.exceptions import ResourceNotFound
from couchexport.properties import TimeStampProperty, JsonProperty
import six
from six.moves import range
from corehq.util.python_compatibility import soft_assert_type_text

ColumnType = namedtuple('ColumnType', 'cls label')
column_types = {}
display_column_types = {}


class register_column_type(object):

    def __init__(self, label=None):
        self.label = label

    def __call__(self, cls):
        column_types[cls.__name__] = cls
        if self.label:
            display_column_types[cls.__name__] = ColumnType(
                cls=cls,
                label=self.label
            )
        return cls


class Format(object):
    """
    Supported formats go here.
    """
    CSV = "csv"
    ZIP = "zip"
    XLS = "xls"
    XLS_2007 = "xlsx"
    HTML = "html"
    ZIPPED_HTML = "zipped-html"
    JSON = "json"
    PYTHON_DICT = "dict"
    UNZIPPED_CSV = 'unzipped-csv'
    CDISC_ODM = 'cdisc-odm'

    FORMAT_DICT = {CSV: {"mimetype": "application/zip",
                         "extension": "zip",
                         "download": True},
                   ZIP: {"mimetype": "application/zip",
                         "extension": "zip",
                         "download": True},
                   XLS: {"mimetype": "application/vnd.ms-excel",
                         "extension": "xls",
                         "download": True},
                   XLS_2007: {"mimetype": "application/vnd.ms-excel",
                              "extension": "xlsx",
                              "download": True},
                   HTML: {"mimetype": "text/html; charset=utf-8",
                          "extension": "html",
                          "download": False},
                   ZIPPED_HTML: {"mimetype": "application/zip",
                                 "extension": "zip",
                                 "download": True},
                   JSON: {"mimetype": "application/json",
                          "extension": "json",
                          "download": False},
                   PYTHON_DICT: {"mimetype": None,
                          "extension": None,
                          "download": False},
                   UNZIPPED_CSV: {"mimetype": "text/csv",
                                  "extension": "csv",
                                  "download": True},
                   CDISC_ODM: {'mimetype': 'application/cdisc-odm+xml',
                               'extension': 'xml',
                               'download': True},

    }

    VALID_FORMATS = list(FORMAT_DICT)

    def __init__(self, slug, mimetype, extension, download):
        self.slug = slug
        self.mimetype = mimetype
        self.extension = extension
        self.download = download

    @classmethod
    def from_format(cls, format):
        format = format.lower()
        if format not in cls.VALID_FORMATS:
            raise URLError("Unsupported export format: %s!" % format)
        return cls(format, **cls.FORMAT_DICT[format])


@register_column_type('plain')
class ExportColumn(DocumentSchema):
    """
    A column configuration, for export
    """
    index = StringProperty()
    display = StringProperty()
    # signature: transform(val, doc) -> val
    transform = SerializableFunctionProperty(default=None)
    tag = StringProperty()
    is_sensitive = BooleanProperty(default=False)
    show = BooleanProperty(default=False)

    @classmethod
    def wrap(self, data):
        if 'is_sensitive' not in data and data.get('transform', None):
            data['is_sensitive'] = True

        if 'doc_type' in data and \
           self.__name__ == ExportColumn.__name__ and \
           self.__name__ != data['doc_type']:
            if data['doc_type'] in column_types:
                return column_types[data['doc_type']].wrap(data)
            else:
                raise ResourceNotFound('Unknown column type: %s', data)
        else:
            return super(ExportColumn, self).wrap(data)

    def get_display(self):
        return '{primary}{extra}'.format(
            primary=self.display,
            extra=" [sensitive]" if self.is_sensitive else ''
        )

    def to_config_format(self, selected=True):
        return {
            "index": self.index,
            "display": self.display,
            "transform": self.transform.dumps() if self.transform else None,
            "is_sensitive": self.is_sensitive,
            "selected": selected,
            "tag": self.tag,
            "show": self.show,
            "doc_type": self.doc_type,
            "options": [],
            "allOptions": None,
        }


class ComplexExportColumn(ExportColumn):
    """
    A single column config that can represent multiple actual columns
    in the excel sheet.
    """

    def get_headers(self):
        """
        Return a list of headers that this column contributes to
        """
        raise NotImplementedError()

    def get_data(self, value):
        """
        Return a list of data values that correspond to the headers
        """
        raise NotImplementedError()


@register_column_type('multi-select')
class SplitColumn(ComplexExportColumn):
    """
    This class is used to split a value into multiple columns based
    on a set of pre-defined options. It splits the data value assuming it
    is space separated.

    The outputs will have one column for each 'option' and one additional
    column for any values from the data don't appear in the options.

    Each column will have a value of 1 if the data value contains the
    option for that column otherwise the column will be blank.

    e.g.
    options = ['a', 'b']
    column_headers = ['col a', 'col b', 'col extra']

    data_val = 'a c d'
    output = [1, '', 'c d']
    """
    options = StringListProperty()
    ignore_extras = False

    def get_headers(self):
        header = self.display if '{option}' in self.display else "{name} | {option}"
        for option in self.options:
            yield header.format(
                name=self.display,
                option=option
            )
        if not self.ignore_extras:
            yield header.format(
                name=self.display,
                option='extra'
            )

    def get_data(self, value):
        from couchexport.export import Constant

        opts_len = len(self.options)
        if isinstance(value, Constant):
            row = [value] * opts_len
        else:
            row = [None] * opts_len

        if not isinstance(value, six.string_types):
            return row if self.ignore_extras else row + [value]
        soft_assert_type_text(value)

        values = value.split(' ') if value else []
        for index, option in enumerate(self.options):
            if option in values:
                row[index] = 1
                values.remove(option)

        if self.ignore_extras:
            return row
        else:
            remainder = ' '.join(values) if values else None
            return row + [remainder]

    def to_config_format(self, selected=True):
        config = super(SplitColumn, self).to_config_format(selected)
        config['options'] = self.options
        return config


class ExportTable(DocumentSchema):
    """
    A table configuration, for export
    """
    index = StringProperty()
    display = StringProperty()
    columns = SchemaListProperty(ExportColumn)

    @classmethod
    def wrap(cls, data):
        # hack: manually remove any references to _attachments at runtime
        data['columns'] = [c for c in data['columns'] if not c['index'].startswith("_attachments.")]
        return super(ExportTable, cls).wrap(data)

    @classmethod
    def default(cls, index):
        return cls(index=index, display="", columns=[])

    @property
    @memoized
    def displays_by_index(self):
        return dict((c.index, c.get_display()) for c in self.columns)

    def get_column_configuration(self, all_cols):
        selected_cols = set()
        for c in self.columns:
            if c.doc_type in display_column_types:
                selected_cols.add(c.index)
                yield c.to_config_format()

        for c in all_cols:
            if c not in selected_cols:
                column = ExportColumn(index=c)
                column.display = self.displays_by_index[c] if c in self.displays_by_index else ''
                yield column.to_config_format(selected=False)

    def get_headers_row(self):
        from couchexport.export import FormattedRow
        headers = []
        for col in self.columns:
            if issubclass(type(col), ComplexExportColumn):
                for header in col.get_headers():
                    headers.append(header)
            else:
                display = col.get_display()
                if col.index == 'id':
                    id_len = len(
                        [part for part in self.index.split('.') if part == '#']
                    )
                    headers.append(display)
                    if id_len > 1:
                        for i in range(id_len):
                            headers.append('{id}__{i}'.format(id=display, i=i))
                else:
                    headers.append(display)
        return FormattedRow(headers)

    @property
    @memoized
    def row_positions_by_index(self):
        return dict((h, i) for i, h in enumerate(self._headers) if h in self.displays_by_index)

    @property
    @memoized
    def id_index(self):
        for i, column in enumerate(self.columns):
            if column.index == 'id':
                return i

    def get_items_in_order(self, row):
        from couchexport.export import scalar_never_was
        row_data = list(row.get_data())
        for column in self.columns:
            # If, for example, column.index references a question in a form
            # export and there are no forms that have a value for that question,
            # then that question does not show up in the schema for the export
            # and so column.index won't be found in self.row_positions_by_index.
            # In those cases we want to give a value of '---' to be consistent
            # with other "not applicable" export values.
            try:
                i = self.row_positions_by_index[column.index]
                val = row_data[i]
            except KeyError:
                val = scalar_never_was

            if issubclass(type(column), ComplexExportColumn):
                for value in column.get_data(val):
                    yield column, value
            else:
                yield column, val

    def trim(self, data, doc, apply_transforms, global_transform):
        from couchexport.export import FormattedRow, Constant, transform_error_constant
        if not hasattr(self, '_headers'):
            self._headers = tuple(data[0].get_data())

        # skip first element without copying
        data = islice(data, 1, None)

        rows = []
        for row in data:
            id = None
            cells = []
            for column, val in self.get_items_in_order(row):
                # TRANSFORM BABY!
                if apply_transforms:
                    if column.transform and not isinstance(val, Constant):
                        try:
                            val = column.transform(val, doc)
                        except Exception:
                            val = transform_error_constant
                    elif global_transform:
                        val = global_transform(val, doc)

                if column.index == 'id':
                    id = val
                else:
                    cells.append(val)
            id_index = self.id_index if id else 0
            row_id = row.id if id else None
            rows.append(FormattedRow(cells, row_id, id_index=id_index))
        return rows


class ExportConfiguration(DocumentSchema):
    """
    Just a way to configure a single export. Used in the group export config.
    """
    index = JsonProperty()
    name = StringProperty()
    format = StringProperty()

    @property
    def filename(self):
        return "%s.%s" % (self.name, Format.from_format(self.format).extension)

    @property
    def type(self):
        # hack - make this backwards compatible with form/case categorization
        # these might only exist in the care-bihar domain or wherever else
        # they've been manually created in the DB.
        try:
            return 'form' if 'http:' in self.index[1] else 'case'
        except IndexError:
            # arbitrarily choose default so it doesn't stay hidden from the UI forever.
            return 'form'

    def __repr__(self):
        return '%s (%s)' % (self.name, self.index)


class SavedBasicExport(BlobMixin, Document):
    pass
