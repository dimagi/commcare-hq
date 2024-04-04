hqDefine("registry/js/registry_actions", [
    'moment',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/bootstrap5/alert_user',
], function (
    moment,
    initialPageData,
    alertUser
) {
    const handleError = function (response) {
        let error = gettext("An unknown error occurred. Please try again or report an issue.");
        if (response.responseJSON && response.responseJSON.error) {
            error = response.responseJSON.error;
        }
        alertUser.alert_user(error, 'danger');
    };

    let accept = function (registrySlug, onSuccess) {
        return acceptOrReject(
            initialPageData.reverse('accept_registry_invitation'),
            registrySlug,
            gettext("Opt in successful"),
            onSuccess
        )
    };

    let reject = function (registrySlug, onSuccess) {
        return acceptOrReject(
            initialPageData.reverse('reject_registry_invitation'),
            registrySlug,
            gettext("Opt out successful"),
            onSuccess
        )
    };

    let acceptOrReject = function (url, registrySlug, successMessage, onSuccess) {
        return $.post({
            url: url,
            data: {registry_slug: registrySlug},
            success: function (data) {
                onSuccess(data);
                alertUser.alert_user(successMessage, 'success');
            },
            error: handleError,
        });
    };

    let manageRelatedModels = function (url, registrySlug, data, onSuccess) {
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
            error: handleError,
        });
    };

    let addInvitations = function (registrySlug, domains, onSuccess) {
        const data = {"action": "add", "domains": domains};
        return manageRelatedModels('manage_invitations', registrySlug, data, onSuccess);
    };

    let removeInvitation = function (registrySlug, invitationId, domain, onSuccess) {
        const data = {"action": "remove", "id": invitationId, "domain": domain};
        return manageRelatedModels('manage_invitations', registrySlug, data, onSuccess);
    };

    let validateName = function (name, onSuccess) {
        return $.post({
            url: initialPageData.reverse('validate_registry_name'),
            data: {name: name},
            success: function (data) {
                onSuccess(data.result);
            },
            error: handleError,
        });
    };

    let editAttr = function (registrySlug, attr, data, onSuccess) {
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
            error: handleError,
        });
    };

    let createGrant = function (registrySlug, domains, onSuccess) {
        const data = {"action": "add", "domains": domains};
        return manageRelatedModels('manage_grants', registrySlug, data, onSuccess);
    };

    let removeGrant = function (registrySlug, grantId, onSuccess) {
        const data = {"action": "remove", "id": grantId};
        return manageRelatedModels('manage_grants', registrySlug, data, onSuccess);
    };

    let loadLogs = function (registrySlug, data, onSuccess) {
        return $.get({
            url: initialPageData.reverse('registry_audit_logs', registrySlug),
            data: data,
            success: function (data) {
                onSuccess(data);
            },
            error: handleError,
        });
    };

    return {
        acceptInvitation: accept,
        rejectInvitation: reject,
        addInvitations: addInvitations,
        removeInvitation: removeInvitation,
        editAttr: editAttr,
        createGrant: createGrant,
        removeGrant: removeGrant,
        validateName: validateName,
        loadLogs: loadLogs,
    };
});
