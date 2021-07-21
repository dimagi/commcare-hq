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

        self.inviteProject = function() {
            console.log("TODO: invite project")
            ko.mapping.fromJS({...registry, rejected_invitation_count: 3}, self);
        }

        self.deleteRegistry = function() {
            console.log("TODO: delete registry", self.name)
        }

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
        self.rejectedText = ko.computed(function() {
            if (self.invitation.status() === 'rejected') {
                return text.getRejectedText(self.invitation);
            }
        });

        self.acceptInvitation = function() {
            console.log("TODO: accept invitation")
            ko.mapping.fromJS({...registry, invitation: {...self.invitation, status: "accepted"}}, self);
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
