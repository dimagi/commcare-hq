from custom.world_vision.reports import TTCReport


class MixedTTCReport(TTCReport):
    report_title = 'Mother/Child Report'
    name = 'Mother/Child Report'
    slug = 'mother_child_report'

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return False