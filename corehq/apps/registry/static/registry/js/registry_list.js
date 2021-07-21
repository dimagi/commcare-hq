hqDefine("registry/js/registry_list", [
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/knockout_bindings.ko', // openModal
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
    let OwnedDataRegistry = function (registry) {
        let self = registry;
        self.acceptedText = getAcceptedText(self);
        self.pendingText = getPendingText(self);
        self.rejectedText = getRejectedText(self);

        self.inviteProject = function() {
            console.log("TODO: invite project")
        }

        self.deleteRegistry = function() {
            console.log("TODO: delete registry", self.name)
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

    let dataRegistryList = function ({ownedRegistries, invitedRegistries}) {
        return {
            ownedRegistries: _.map(ownedRegistries, (registry) => OwnedDataRegistry(registry)),
            invitedRegistries: _.map(invitedRegistries, (registry) => InvitedDataRegistry(registry)),
            newRegistry: function() {
                console.log("TODO: New Registry");
            }
        }
    }
    $(function () {
        $("#data-registry-list").koApplyBindings(dataRegistryList({
            ownedRegistries: initialPageData.get("owned_registries"),
            invitedRegistries: initialPageData.get("invited_registries"),
        }));
    });
});
