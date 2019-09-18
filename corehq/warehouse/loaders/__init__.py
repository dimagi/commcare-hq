from corehq.warehouse.loaders.domain import DomainStagingLoader, DomainDimLoader


def get_loader_by_slug(slug):
    return {
        cls.slug: cls for cls in [
            DomainStagingLoader,
            DomainDimLoader
        ]
    }[slug]
