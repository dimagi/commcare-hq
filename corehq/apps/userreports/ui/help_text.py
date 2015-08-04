from django.utils.translation import ugettext_lazy as _

TABLE_ID = _(
    "Choose something short, unique, and memorable using "
    "lowercase letters, numbers, and underscores")
DISPLAY_NAME = _(
    "This is what the data source will be called in navigation, page title, etc.")
DESCRIPTION = _(
    "Write yourself a little note if you like, it's optional")
BASE_ITEM_EXPRESSION = _(
    'You can leave this blank unless you are '
    '<a target="_blank" href="'
    'https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/userreports/README.md#saving-repeat-data'
    '">saving repeat data</a>')
CONFIGURED_FILTER = _(
    'Look at '
    '<a target="_blank" href="'
    'https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/userreports/examples/examples.md#data-source-filters'
    '">these examples</a> and '
    '<a target="_blank" href="'
    'https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/userreports/README.md#data-source-filtering'
    '">these docs</a>')
CONFIGURED_INDICATORS = _(
    'Look at '
    '<a target="_blank" href="'
    'https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/userreports/examples/examples.md#data-source-indicators'
    '">these examples</a> and '
    '<a target="_blank" href="'
    'https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/userreports/README.md#indicators'
    '">these docs</a>')
NAMED_FILTER = _(
    'For this advanced and useful feature, '
    'give a dict where the keys are the variable names you choose '
    'and the values are filters according to the syntax of '
    'Configured Filters above. You can then reference these from '
    'Configured Filters as {"type": "named", "name": "myvarname"}')
