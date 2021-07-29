hqDefine("registry/js/registry_list", [
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/alert_user',
    'registry/js/registry_text',
    'registry/js/registry_actions',
    'hqwebapp/js/knockout_bindings.ko', // openModal
], function (
    $,
    _,
    ko,
    initialPageData,
    alertUser,
    text,
    actions
) {

    let OwnedDataRegistry = function (registry) {
        let self = ko.mapping.fromJS(registry);
        self.acceptedText = ko.computed(function() {
            return text.getAcceptedBadgeText(self);
        });
        self.pendingText = ko.computed(function() {
            return text.getPendingBadgeText(self);
        });
        self.rejectedText = ko.computed(function() {
            return text.getRejectedBadgeText(self);
        });
        self.manageUrl = initialPageData.reverse('manage_registry', self.slug())

        return self;
    };

    let InvitedDataRegistry = function (registry) {
        let self = ko.mapping.fromJS(registry);
        self.participatorCountText = ko.computed(function() {
            return text.getParticipatorCountBadgeText(self);
        });
        self.statusText = ko.computed(function() {
            return text.getStatusText(self.invitation.status());
        });

        self.manageUrl = initialPageData.reverse('manage_registry', self.slug())

        self.acceptInvitation = function() {
            actions.acceptInvitation(self.slug, (data) => {
                ko.mapping.fromJS(data, self);
            });
        }

        self.rejectInvitation = function() {
            actions.rejectInvitation(self.slug, (data) => {
                ko.mapping.fromJS(data, self);
            });
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
