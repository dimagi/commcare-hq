from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf import settings

from compressor.filters import CompilerFilter
from compressor.filters.css_default import CssAbsoluteFilter


class LessFilter(CompilerFilter):

    def __init__(self, content, attrs, **kwargs):
        super(LessFilter, self).__init__(content,
                                         command='{lessc} {infile} {outfile}',
                                         **kwargs)

    def input(self, **kwargs):
        if "{lessc}" in self.command:
            options = list(self.options)

            # interim use b3 lessc path until final switchover
            lessc_path = 'lessc'

            options.append(('lessc', lessc_path))
            self.options = tuple(options)

        content = super(LessFilter, self).input(**kwargs)
        # process absolute file paths
        return CssAbsoluteFilter(content).input(**kwargs)

