hqDefine("registry/js/registry_list", [
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    _,
    ko,
    initialPageData
) {
    let getBadgeText = function (count, singular, plural) {
        return interpolate(ngettext(singular, plural, count), {"count": count}, true);
    }
    let getAcceptedText = function(registry) {
        return getBadgeText(
            registry.accepted_invitation_count,
            "%(count)s Invitation Accepted",
            "%(count)s Invitations Accepted",
        )
    }
    let getPendingText = function(registry) {
        return getBadgeText(
            registry.pending_invitation_count,
            "%(count)s Invitation Pending",
            "%(count)s Invitations Pending",
        )
    }
    let getRejectedText = function(registry) {
        return getBadgeText(
            registry.rejected_invitation_count,
            "%(count)s Invitation Rejected",
            "%(count)s Invitations Rejected",
        )
    }
    let getParticipatorCountText = function(registry) {
        return getBadgeText(
            registry.participator_count,
            "%(count)s Project Space Participating",
            "%(count)s Project Spaces Participating",
        )
    }
    let DeleteModal = function (element) {
        let self = {
            registryName: ko.observable(),
            registryId: ko.observable(),
        };
        self.show = function(registry) {
            self.registryName(registry.name);
            self.registryId(registry.id);
            element.modal('show');
        }
        self.deleteRegistry = function() {
            console.log("TODO: delete registry", self.registryId)
            element.modal('hide');
        }
        return self;
    }
    let OwnedDataRegistry = function (registry, deleteModal) {
        let self = registry;
        self.acceptedText = getAcceptedText(self);
        self.pendingText = getPendingText(self);
        self.rejectedText = getRejectedText(self);

        self.showDeleteModal = function() {
            deleteModal.show(self);
        }

        self.inviteProject = function() {
            console.log("TODO: invite project")
        }

        return self;
    };

    let InvitedDataRegistry = function (registry) {
        let self = registry;
        self.participatorCountText = getParticipatorCountText(self);

        self.acceptInvitation = function() {
            console.log("TODO: accept invitation")
        }

        self.rejectInvitation = function() {
            console.log("TODO: reject invitation")
        }
        return self;
    };

    let dataRegistryList = function ({ownedRegistries, invitedRegistries, deleteModal}) {
        return {
            ownedRegistries: _.map(ownedRegistries, (registry) => OwnedDataRegistry(registry, deleteModal)),
            invitedRegistries: _.map(invitedRegistries, (registry) => InvitedDataRegistry(registry)),
            newRegistry: function() {
                console.log("TODO: New Registry");
            }
        }
    }
    $(function () {
        let modalElement = $("#delete-registry-modal"),
            deleteModal = DeleteModal(modalElement);
        modalElement.koApplyBindings(deleteModal);
        $("#data-registry-list").koApplyBindings(dataRegistryList({
            ownedRegistries: initialPageData.get("owned_registries"),
            invitedRegistries: initialPageData.get("invited_registries"),
            deleteModal: deleteModal,
        }));
    });
});
