import StringIO
import urllib2
from corehq.apps.app_manager.views import download_app_strings
from dimagi.utils.django.cached_object import CachedObject
from django.core.servers.basehttp import FileWrapper
from django.http import HttpResponse
from django.views.generic import View


class RedisAssetsAPI(View):
    def get(self, *args, **kwargs):
        filename = str(self.request.GET.get('file'))
        obj = CachedObject(filename)

        if not obj.is_cached():
            text = "AAA"
            buffer = StringIO.StringIO(text)
            metadata = {'content_type': 'text/plain'}
            obj.cache_put(buffer, metadata)
        else:
            #raise ValueError("is cached")
            pass

        cmeta, cstream = obj.get()
        #####################
        wrapper = FileWrapper(cstream)
        if cmeta is not None:
            mime_type = cmeta['content_type']
        else:
            mime_type = "plain/text"
        response = HttpResponse(wrapper, mimetype=mime_type)
        return response