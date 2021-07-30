hqDefine("registry/js/registry_actions", [
    'moment',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/alert_user',
], function (
    moment,
    initialPageData,
    alertUser
) {
    let accept = function(registrySlug, onSuccess) {
        return acceptOrReject(
            initialPageData.reverse('accept_registry_invitation'),
            registrySlug,
            onSuccess
        )
    }

    let reject = function(registrySlug, onSuccess) {
        return acceptOrReject(
            initialPageData.reverse('reject_registry_invitation'),
            registrySlug,
            onSuccess
        )
    }

    let acceptOrReject = function(url, registrySlug, onSuccess) {
        return $.post({
            url: url,
            data: {registry_slug: registrySlug},
            success: function (data) {
                onSuccess(data);
                alertUser.alert_user(gettext("Invitation accepted"), 'success');
            },
            error: function (response) {
                alertUser.alert_user(response.responseJSON.error, 'danger');
            },
        });
    }

    let manageRelatedModels = function(url, registrySlug, data, onSuccess) {
        return $.post({
            url: initialPageData.reverse(url, registrySlug),
            data: data,
            traditional: true,
            success: function (data) {
                onSuccess(data);
                if (data.message) {
                    alertUser.alert_user(data.message, 'success');
                }
            },
            error: function (response) {
                alertUser.alert_user(response.responseJSON.error, 'danger');
            },
        });
    }

    let addInvitations = function (registrySlug, domains, onSuccess) {
        const data = {"action": "add", "domains": domains};
        return manageRelatedModels('manage_invitations', registrySlug, data, onSuccess);
    }

    let removeInvitation = function (registrySlug, invitationId, domain, onSuccess) {
        const data = {"action": "remove", "id": invitationId, "domain": domain};
        return manageRelatedModels('manage_invitations', registrySlug, data, onSuccess);
    }

    let editAttr = function(registrySlug, attr, data, onSuccess) {
        return $.post({
            url: initialPageData.reverse('edit_registry_attr', registrySlug, attr),
            data: data,
            traditional: true,
            success: function (data) {
                onSuccess(data);
                if (data.message) {
                    alertUser.alert_user(data.message, 'success');
                }
            },
            error: function (response) {
                let error = gettext("An unknown error occurred. Please try again or report an issue.");
                if (response.responseJSON.error) {
                    error = response.responseJSON.error;
                }
                alertUser.alert_user(error, 'danger');
            },
        });
    }

    let createGrant = function (registrySlug, domains, onSuccess) {
        const data = {"action": "add", "domains": domains};
        return manageRelatedModels('manage_grants', registrySlug, data, onSuccess);
    }

    let removeGrant = function (registrySlug, grantId, onSuccess) {
        const data = {"action": "remove", "id": grantId};
        return manageRelatedModels('manage_grants', registrySlug, data, onSuccess);
    }

    return {
        acceptInvitation: accept,
        rejectInvitation: reject,
        addInvitations: addInvitations,
        removeInvitation: removeInvitation,
        editAttr: editAttr,
        createGrant: createGrant,
        removeGrant: removeGrant,
    };
});
