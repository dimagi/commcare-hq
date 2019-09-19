from corehq.warehouse.loaders.app_status import (
    ApplicationStatusFactLoader,
    AppStatusFormStagingLoader,
    AppStatusSynclogStagingLoader,
)
from corehq.warehouse.loaders.application import (
    ApplicationDimLoader,
    ApplicationStagingLoader,
)
from corehq.warehouse.loaders.domain import (
    DomainDimLoader,
    DomainStagingLoader,
)
from corehq.warehouse.loaders.form import FormFactLoader, FormStagingLoader
from corehq.warehouse.loaders.group import GroupDimLoader, GroupStagingLoader
from corehq.warehouse.loaders.location import (
    LocationDimLoader,
    LocationStagingLoader,
)
from corehq.warehouse.loaders.synclog import (
    SyncLogFactLoader,
    SyncLogStagingLoader,
)
from corehq.warehouse.loaders.user import UserDimLoader, UserStagingLoader


def get_loader_by_slug(slug):
    loaders = [
        DomainStagingLoader,
        DomainDimLoader,
        UserStagingLoader,
        UserDimLoader,
        GroupStagingLoader,
        GroupDimLoader,
        LocationStagingLoader,
        LocationDimLoader,
        ApplicationStagingLoader,
        ApplicationDimLoader,

        FormStagingLoader,
        FormFactLoader,
        SyncLogStagingLoader,
        SyncLogFactLoader,

        AppStatusSynclogStagingLoader,
        AppStatusFormStagingLoader,
        ApplicationStatusFactLoader,
    ]
    return {cls.slug: cls for cls in loaders}[slug]
