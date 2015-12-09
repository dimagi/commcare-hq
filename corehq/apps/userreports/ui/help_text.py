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
    'https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/userreports/README.md#saving-multiple-rows-per-caseform'
    '">saving multiple rows per case or form</a>')
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
NAMED_EXPRESSIONS = _(
    'For this advanced and useful feature, '
    'give a dict where the keys are the variable names you choose '
    'and the values are any valid expressions. You can then reference these from filters and indicators '
    'wherever an expression goes using: <code>{"type": "named", "name": "myvarname"}</code>')
NAMED_FILTER = _('These behave exactly like named expressions (see above), except the values '
                 'should be a valid filter, and they can be used wherever filters are used above.')
