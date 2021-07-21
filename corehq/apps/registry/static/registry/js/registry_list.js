hqDefine("registry/js/registry_list", [
    'jquery',
    'underscore',
    'knockout',
    'moment',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/knockout_bindings.ko', // openModal
], function (
    $,
    _,
    ko,
    moment,
    initialPageData
) {
    let getAcceptedBadgeText = function(registry) {
        return interpolate(ngettext(
            "%(count)s Invitation Accepted",
            "%(count)s Invitations Accepted",
            registry.accepted_invitation_count
        ), {"count": registry.accepted_invitation_count}, true);
    }
    let getPendingBadgeText = function(registry) {
        return interpolate(ngettext(
            "%(count)s Invitation Pending",
            "%(count)s Invitations Pending",
            registry.pending_invitation_count
        ), {"count": registry.pending_invitation_count}, true);
    }
    let getRejectedBadgeText = function(registry) {
        return interpolate(ngettext(
            "%(count)s Invitation Rejected",
            "%(count)s Invitations Rejected",
            registry.rejected_invitation_count
        ), {"count": registry.rejected_invitation_count}, true);
    }
    let getParticipatorCountBadgeText = function(registry) {
        return interpolate(ngettext(
            "%(count)s Project Space Participating",
            "%(count)s Project Spaces Participating",
            registry.participator_count
        ), {"count": registry.participator_count}, true);
    }
    let getStatusText = function(registry) {
        if (registry.invitation.status === 'rejected') {
            return gettext('Rejected')   ;
        } else if (registry.invitation.status === 'accepted') {
            return gettext('Accepted');
        } else {
            return gettext('Pending');
        }
    }
    let getRejectedText = function(registry) {
        console.log(registry.invitation);
        const text = gettext("Rejected by %(user)s on %(date)s"),
            params = {
                user: registry.invitation.rejected_by,
                date: moment(registry.invitation.rejected_on).format("D MMM YYYY")
            };
        return interpolate(text, params, true);
    }
    let OwnedDataRegistry = function (registry) {
        let self = registry;
        self.acceptedText = getAcceptedBadgeText(self);
        self.pendingText = getPendingBadgeText(self);
        self.rejectedText = getRejectedBadgeText(self);

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
        self.participatorCountText = getParticipatorCountBadgeText(self);
        self.statusText = getStatusText(self);
        if (self.invitation.status === 'rejected') {
            self.rejectedText = getRejectedText(self);
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
