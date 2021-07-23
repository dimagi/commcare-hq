hqDefine("registry/js/registry_actions", [
    'moment',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/alert_user',
], function (
    moment,
    initialPageData,
    alertUser,
) {
    let accept = function(registrySlug, onSuccess) {
        acceptOrReject(
            initialPageData.reverse('accept_registry_invitation'),
            registrySlug,
            onSuccess
        )
    }

    let reject = function(registrySlug, onSuccess) {
        acceptOrReject(
            initialPageData.reverse('reject_registry_invitation'),
            registrySlug,
            onSuccess
        )
    }

    let acceptOrReject = function(url, registrySlug, onSuccess) {
        $.post({
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

    let editAttr = function(registrySlug, attr, data, onSuccess) {
        $.post({
            url: initialPageData.reverse('edit_registry_attr', registrySlug, attr),
            data: data,
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

    return {
        acceptInvitation: accept,
        rejectInvitation: reject,
        editAttr: editAttr
    };
});
