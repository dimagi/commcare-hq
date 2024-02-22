hqDefine("registry/js/registry_text", [], function () {
    let getAcceptedBadgeText = function (registry) {
        return interpolate(ngettext(
            "%(count)s Invitation Accepted",
            "%(count)s Invitations Accepted",
            registry.accepted_invitation_count()
        ), {"count": registry.accepted_invitation_count()}, true);
    };
    let getPendingBadgeText = function (registry) {
        return interpolate(ngettext(
            "%(count)s Invitation Pending",
            "%(count)s Invitations Pending",
            registry.pending_invitation_count()
        ), {"count": registry.pending_invitation_count()}, true);
    };
    let getRejectedBadgeText = function (registry) {
        return interpolate(ngettext(
            "%(count)s Invitation Rejected",
            "%(count)s Invitations Rejected",
            registry.rejected_invitation_count()
        ), {"count": registry.rejected_invitation_count()}, true);
    };
    let getParticipatorCountBadgeText = function (registry) {
        return interpolate(ngettext(
            "%(count)s Project Space Participating",
            "%(count)s Project Spaces Participating",
            registry.participator_count()
        ), {"count": registry.participator_count()}, true);
    };
    let getStatusText = function (status) {
        if (status === 'rejected') {
            return gettext('Rejected');
        } else if (status === 'accepted') {
            return gettext('Accepted');
        } else {
            return gettext('Pending');
        }
    };
    let getStatusIcon = function (status) {
        if (status === 'rejected') {
            return gettext('fa-ban');
        } else if (status === 'accepted') {
            return gettext('fa-regular fa-clock');
        } else {
            return gettext('fa-regular fa-circle-check');
        }
    };
    let getStatusCssClass = function (status) {
        if (status === 'rejected') {
            return gettext('label-warning-light');
        } else if (status === 'accepted') {
            return gettext('label-success-light');
        } else {
            return gettext('label-info-light');
        }
    };

    return {
        getAcceptedBadgeText: getAcceptedBadgeText,
        getPendingBadgeText: getPendingBadgeText,
        getRejectedBadgeText: getRejectedBadgeText,
        getParticipatorCountBadgeText: getParticipatorCountBadgeText,
        getStatusText: getStatusText,
        getStatusIcon: getStatusIcon,
        getStatusCssClass: getStatusCssClass,
    };
});
