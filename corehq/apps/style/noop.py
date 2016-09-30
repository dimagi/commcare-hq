import os
import subprocess
from django.conf import settings

from compressor.exceptions import FilterError
from compressor.filters import CompilerFilter
from compressor.js import JsCompressor
from compressor.utils.stringformat import FormattableString as fstr
from django.conf import settings
from django.utils.safestring import mark_safe


class JsNoopCompressor(JsCompressor):

    def output(self, mode='file', forced=False):
        return ''

    def output_file(self, mode, new_filepath):
        """
        The output method that saves the content to a file and renders
        the appropriate template with the file's URL.
        """
        url = mark_safe(self.storage.url(new_filepath))
        return self.render_output(mode, {"url": url})
