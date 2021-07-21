hqDefine("registry/js/registry_text", ['moment'], function (moment) {
    let getAcceptedBadgeText = function (registry) {
        return interpolate(ngettext(
            "%(count)s Invitation Accepted",
            "%(count)s Invitations Accepted",
            registry.accepted_invitation_count()
        ), {"count": registry.accepted_invitation_count()}, true);
    }
    let getPendingBadgeText = function (registry) {
        return interpolate(ngettext(
            "%(count)s Invitation Pending",
            "%(count)s Invitations Pending",
            registry.pending_invitation_count()
        ), {"count": registry.pending_invitation_count()}, true);
    }
    let getRejectedBadgeText = function (registry) {
        return interpolate(ngettext(
            "%(count)s Invitation Rejected",
            "%(count)s Invitations Rejected",
            registry.rejected_invitation_count()
        ), {"count": registry.rejected_invitation_count()}, true);
    }
    let getParticipatorCountBadgeText = function (registry) {
        return interpolate(ngettext(
            "%(count)s Project Space Participating",
            "%(count)s Project Spaces Participating",
            registry.participator_count()
        ), {"count": registry.participator_count()}, true);
    }
    let getStatusText = function (status) {
        if (status === 'rejected') {
            return gettext('Rejected');
        } else if (status === 'accepted') {
            return gettext('Accepted');
        } else {
            return gettext('Pending');
        }
    }
    let getRejectedText = function (invitation) {
        const text = gettext("Rejected by %(user)s on %(date)s"),
            params = {
                user: invitation.rejected_by(),
                date: moment(invitation.rejected_on()).format("D MMM YYYY")
            };
        return interpolate(text, params, true);
    }

    return {
        getAcceptedBadgeText: getAcceptedBadgeText,
        getPendingBadgeText: getPendingBadgeText,
        getRejectedBadgeText: getRejectedBadgeText,
        getParticipatorCountBadgeText: getParticipatorCountBadgeText,
        getStatusText: getStatusText,
        getRejectedText: getRejectedText,
    };
});
