from corehq.warehouse.loaders.application import ApplicationStagingLoader, ApplicationDimLoader
from corehq.warehouse.loaders.domain import DomainStagingLoader, DomainDimLoader
from corehq.warehouse.loaders.form import FormStagingLoader, FormFactLoader
from corehq.warehouse.loaders.group import GroupStagingLoader, GroupDimLoader
from corehq.warehouse.loaders.location import LocationStagingLoader, LocationDimLoader
from corehq.warehouse.loaders.synclog import SyncLogStagingLoader, SyncLogFactLoader
from corehq.warehouse.loaders.user import UserStagingLoader, UserDimLoader


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
    ]
    return {cls.slug: cls for cls in loaders}[slug]
