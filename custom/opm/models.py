"""
Fluff IndicatorDocument definitions for the OPM reports.
"""
from corehq.apps.change_feed import topics
from fluff.filters import CustomFilter
from corehq.apps.users.models import CommCareUser
import fluff

# OpmUserFluff is unusual in that it stores only flat information about a
# specific case or user - no aggregation will be performed
from custom.utils.utils import flat_field


# This calculator is necessary to generate 'date' field which is required in the database
class Numerator(fluff.Calculator):
    @fluff.null_emitter
    def numerator(self, doc):
        yield None


def is_valid_user(user):
    if not (user.is_active and user.base_doc == "CouchUser"):
        return False
    for key in ('awc', 'gp', 'block'):
        if not user.user_data.get(key, False):
            return False
    return True


class OpmUserFluff(fluff.IndicatorDocument):
    def user_data(property):
        """
        returns a flat field with a callable looking for `property` on the user
        """
        return flat_field(lambda user: user.user_data.get(property))

    document_class = CommCareUser
    domains = ('opm',)
    group_by = ('domain', )
    # Only consider active users
    document_filter = CustomFilter(is_valid_user)

    save_direct_to_sql = True
    kafka_topic = topics.META

    name = flat_field(lambda user: user.name)

    numerator = Numerator()
    awc_code = user_data('awc_code')
    bank_name = user_data('bank_name')
    ifs_code = user_data('ifs_code')
    account_number = user_data('account_number')
    awc = user_data('awc')
    block = user_data('block')
    gp = user_data('gp')
    village = user_data('village')
    gps = user_data('gps')

    class Meta:
        app_label = 'opm'


OpmUserFluffPillow = OpmUserFluff.pillow()
