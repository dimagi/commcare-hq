hqDefine('sso/js/new_identity_provider', [
    'jquery',
    'accounting/js/widgets',
], function (
    $,
    widgets
) {

    var identityProviderModel = function () {
        'use strict';
        var self = {};

        self.owner = widgets.asyncSelect2Handler('owner', false, 'select2_identity_provider');

        self.init = function () {
            self.owner.init();
        };

        return self;
    };

    $(function () {
        var identityProviderHandler = identityProviderModel();
        identityProviderHandler.init();
    });
});
