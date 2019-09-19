from corehq.warehouse.loaders.domain import DomainStagingLoader, DomainDimLoader
from corehq.warehouse.loaders.user import UserStagingLoader, UserDimLoader


def get_loader_by_slug(slug):
    loaders = [
        DomainStagingLoader,
        DomainDimLoader,
        UserStagingLoader,
        UserDimLoader,
    ]
    return {cls.slug: cls for cls in loaders}[slug]
