from django.utils.translation import gettext_lazy as _

USER_QUERY_LIMIT = 5000
DEFAULT_PAGE_LIMIT = 10

TABLEAU_ROLES = (
    (_('Explorer - Can Publish'), 'ExplorerCanPublish'),
    (_('Server Administrator'), 'ServerAdministrator'),
    (_('Site Administrator - Explorer'), 'SiteAdministratorExplorer'),
    (_('Site Administrator - Creator'), 'SiteAdministratorCreator'),
    (_('Unlicensed'), 'Unlicensed'),
    (_('Read Only'), 'ReadOnly'),
    (_('Viewer'), 'Viewer')
)

HQ_TABLEAU_GROUP_NAME = 'HQ'
