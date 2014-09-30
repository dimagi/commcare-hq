from compressor.filters import CompilerFilter
from compressor.filters.css_default import CssAbsoluteFilter
import settings


class LessFilter(CompilerFilter):
    def __init__(self, content, attrs, **kwargs):
        super(LessFilter, self).__init__(content,
                                         command='{lessc} {infile} {outfile}',
                                         **kwargs)

    def input(self, **kwargs):
        if "{lessc}" in self.command:
            options = list(self.options)
            lessc_path = 'lessc'
            filename = self.filename.split('/')[-1]
            # for handling the migration to Bootstrap 3
            if filename not in [
                'hqstyle-core.less',
                'hqstyle-mobile-c2.less',
                'app_manager.less',
                'core.less',
            ]:
                lessc_path = settings.LESS_FOR_BOOTSTRAP_3_BINARY
            options.append(('lessc', lessc_path))
            self.options = tuple(options)

        content = super(LessFilter, self).input(**kwargs)
        # process absolute file paths
        return CssAbsoluteFilter(content).input(**kwargs)

