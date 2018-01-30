from __future__ import absolute_import
from corehq.warehouse.models.dimensions import (
    UserDim,
    GroupDim,
    LocationDim,
    DomainDim,
    UserLocationDim,
    DomainMembershipDim,
    UserGroupDim,
    ApplicationDim
)

from corehq.warehouse.models.meta import (
    Batch,
    CommitRecord,
)

from corehq.warehouse.models.facts import (
    ApplicationStatusFact,
    FormFact,
)

from corehq.warehouse.models.staging import (
    GroupStagingTable,
    DomainStagingTable,
    UserStagingTable,
    FormStagingTable,
    SyncLogStagingTable,
    LocationStagingTable,
    LocationTypeStagingTable,
    ApplicationStagingTable
)


def get_cls_by_slug(slug):
    return {
        GroupStagingTable.slug: GroupStagingTable,
        DomainStagingTable.slug: DomainStagingTable,
        UserStagingTable.slug: UserStagingTable,
        FormStagingTable.slug: FormStagingTable,
        SyncLogStagingTable.slug: SyncLogStagingTable,
        LocationStagingTable.slug: LocationStagingTable,
        LocationTypeStagingTable.slug: LocationTypeStagingTable,
        ApplicationStagingTable.slug: ApplicationStagingTable,

        UserDim.slug: UserDim,
        GroupDim.slug: GroupDim,
        LocationDim.slug: LocationDim,
        DomainDim.slug: DomainDim,
        UserLocationDim.slug: UserLocationDim,
        DomainMembershipDim.slug: DomainMembershipDim,
        UserGroupDim.slug: UserGroupDim,
        ApplicationDim.slug: ApplicationDim,

        ApplicationStatusFact.slug: ApplicationStatusFact,
        FormFact.slug: FormFact,
    }[slug]
