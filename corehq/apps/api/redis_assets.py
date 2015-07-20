import StringIO
from dimagi.utils.django.cached_object import CachedObject
from django.core.servers.basehttp import FileWrapper
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.generic import View


VALID_FILENAMES = [
    'default/app_strings.txt',
    'en/app_strings.txt',
    'media_profile.ccpr',
    'media_profile.xml',
    'media_suite.xml',
    'modules-0/forms-0.xml',
    'modules-0/forms-1.xml',
    'modules-0/forms-2.xml',
    'modules-0/forms-3.xml',
    'modules-0/forms-4.xml',
    'modules-0/forms-5.xml',
    'modules-1/forms-0.xml',
    'modules-1/forms-1.xml',
    'modules-1/forms-2.xml',
    'modules-1/forms-3.xml',
    'modules-1/forms-4.xml',
    'modules-2/forms-0.xml',
    'modules-3/forms-0.xml',
    'modules-4/forms-0.xml',
    'modules-4/forms-1.xml',
    'modules-4/forms-2.xml',
    'modules-5/forms-0.xml',
    'modules-6/forms-0.xml',
    'modules-7/forms-0.xml',
    'modules-7/forms-1.xml',
    'modules-7/forms-2.xml',
    'modules-8/forms-0.xml',
    'modules-8/forms-1.xml',
    'modules-8/forms-2.xml',
    'modules-9/forms-0.xml',
    'profile.ccpr',
    'profile.xml',
    'suite.xml',
]


class RedisAssetsAPI(View):
    def get(self, *args, **kwargs):
        filename = str(self.request.GET.get('file'))
        if not filename in VALID_FILENAMES:
            return HttpResponseBadRequest('invalid filename=' + filename)
        obj = CachedObject(filename)

        if not obj.is_cached():
            f = open('corehq/apps/api/data/' + filename, 'r')
            text = f.read()
            f.close()
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
        response = HttpResponse(wrapper, content_type=mime_type)
        return response
