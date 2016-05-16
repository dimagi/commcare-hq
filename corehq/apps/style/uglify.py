import os
import subprocess
from django.conf import settings

from compressor.exceptions import FilterError
from compressor.filters import CompilerFilter
from compressor.js import JsCompressor
from compressor.utils.stringformat import FormattableString as fstr
from django.conf import settings
from django.utils.safestring import mark_safe


# For use with node.js' uglifyjs minifier
# Code taken from: https://roverdotcom.github.io/blog/2014/05/28/javascript-error-reporting-with-source-maps-in-django/
class UglifySourcemapFilter(CompilerFilter):
    command = (
        "uglifyjs {infiles} -o {outfile} --source-map {mapfile}"
        " --source-map-url {mapurl} --source-map-root {maproot} -c -m")

    def input(self, **kwargs):
        return self.content

    def output(self, **kwargs):
        options = dict(self.options)
        options['outfile'] = kwargs['outfile']

        infiles = []
        for infile in kwargs['content_meta']:
            # type, full_filename, relative_filename
            # In debug mode we use the full path so that in development we see changes without having to call
            # collectstatic. This breaks the sourcemaps. In production, we want  sourcemaps to work so we
            # use relative path which will take files from `staticfiles` automatically.
            if settings.DEBUG:
                infiles.append(infile[1])
            else:
                infiles.append(infile[2])

        options['infiles'] = ' '.join(f for f in infiles)

        options['mapfile'] = kwargs['outfile'].replace('.js', '.map.js')

        options['mapurl'] = '{}{}'.format(
            settings.STATIC_URL, options['mapfile']
        )

        options['maproot'] = settings.STATIC_URL

        self.cwd = kwargs['root_location']

        try:
            command = fstr(self.command).format(**options)

            proc = subprocess.Popen(
                command, shell=True, cwd=self.cwd, stdout=self.stdout,
                stdin=self.stdin, stderr=self.stderr)
            err = proc.communicate()
        except (IOError, OSError), e:
            raise FilterError('Unable to apply %s (%r): %s' %
                              (self.__class__.__name__, self.command, e))
        else:
            # If the process doesn't return a 0 success code, throw an error
            if proc.wait() != 0:
                if not err:
                    err = ('Unable to apply %s (%s)' %
                           (self.__class__.__name__, self.command))
                raise FilterError(err)
            if self.verbose:
                self.logger.debug(err)


class JsUglifySourcemapCompressor(JsCompressor):

    def output(self, mode='file', forced=False):
        content = self.filter_input(forced)
        if not content:
            return ''

        concatenated_content = '\n'.join(
            c.encode(self.charset) for c in content)

        if settings.COMPRESS_ENABLED or forced:
            js_compress_dir = os.path.join(
                settings.STATIC_ROOT, self.output_dir, self.output_prefix
            )
            if not os.path.exists(js_compress_dir):
                os.makedirs(js_compress_dir, 0775)
            filepath = self.get_filepath(concatenated_content, basename=None)

            # UglifySourcemapFilter writes the file directly, as it needs to
            # output the sourcemap as well. Only write the file if it doesn't
            # already exist
            if not os.path.exists(os.path.join(settings.STATIC_ROOT, filepath)):
                UglifySourcemapFilter(content).output(
                    outfile=filepath,
                    content_meta=self.split_content,
                    root_location=self.storage.base_location)

            return self.output_file(mode, filepath)
        else:
            return concatenated_content

    def output_file(self, mode, new_filepath):
        """
        The output method that saves the content to a file and renders
        the appropriate template with the file's URL.
        """
        url = mark_safe(self.storage.url(new_filepath))
        return self.render_output(mode, {"url": url})
