from django.utils.translation import gettext_lazy as _

USER_QUERY_LIMIT = 5000
DEFAULT_PAGE_LIMIT = 10

TABLEAU_ROLES = (
    ('Explorer', _('Explorer')),
    ('ExplorerCanPublish', _('Explorer - Can Publish')),
    ('ServerAdministrator', _('Server Administrator')),
    ('SiteAdministratorExplorer', _('Site Administrator - Explorer')),
    ('SiteAdministratorCreator', _('Site Administrator - Creator')),
    ('Unlicensed', _('Unlicensed')),
    ('ReadOnly', _('Read Only')),
    ('Viewer', _('Viewer'))
)

HQ_TABLEAU_GROUP_NAME = 'HQ'

LONG_RUNNING_CLE_THRESHOLD = 10
