hqDefine("registry/js/registry_list", [
    'jquery',
    'underscore',
    'knockout',
    'moment',
    'hqwebapp/js/initial_page_data',
    'registry/js/registry_text',
    'hqwebapp/js/knockout_bindings.ko', // openModal
], function (
    $,
    _,
    ko,
    moment,
    initialPageData,
    text,
) {

    let OwnedDataRegistry = function (registry) {
        let self = registry;
        self.acceptedText = text.getAcceptedBadgeText(self);
        self.pendingText = text.getPendingBadgeText(self);
        self.rejectedText = text.getRejectedBadgeText(self);

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
        self.participatorCountText = text.getParticipatorCountBadgeText(self);
        self.statusText = text.getStatusText(self);
        if (self.invitation.status === 'rejected') {
            self.rejectedText = text.getRejectedText(self);
        }

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
