class HealthStatusMixin(object):

    @property
    def blocks(self):
        return self.request.GET.getlist('blocks', [])

    @property
    def awcs(self):
        return self.request.GET.getlist('awcs', [])