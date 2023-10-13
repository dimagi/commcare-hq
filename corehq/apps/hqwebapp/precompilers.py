import os

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
            lessc_path = os.path.join(
                settings.BASE_DIR, 'node_modules', 'less', 'bin', 'lessc')

            options.append(('lessc', lessc_path))
            self.options = tuple(options)

        content = super(LessFilter, self).input(**kwargs)
        # process absolute file paths
        return CssAbsoluteFilter(content).input(**kwargs)


class SassFilter(CompilerFilter):

    def __init__(self, content, attrs, **kwargs):
        super(SassFilter, self).__init__(content,
                                         command='sass {infile} {outfile} '
                                                 '--load-path=node_modules/bootstrap5/scss',
                                         **kwargs)

    def input(self, **kwargs):
        content = super(SassFilter, self).input(**kwargs)
        # process absolute file paths
        return CssAbsoluteFilter(content).input(**kwargs)
