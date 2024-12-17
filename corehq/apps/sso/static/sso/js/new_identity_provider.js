hqDefine('sso/js/new_identity_provider', [
    'jquery',
    'knockout',
    'accounting/js/widgets',
    'hqwebapp/js/initial_page_data',
    'commcarehq',
], function (
    $,
    ko,
    widgets,
    initialPageData
) {

    var identityProviderModel = function () {
        'use strict';
        var self = {};

        self.owner = widgets.asyncSelect2Handler('owner', false, 'select2_identity_provider');
        self.protocol = ko.observable('saml');
        self.idpTypesByProtocol = initialPageData.get('idp_types_by_protocol');
        self.availableIdpTypes = ko.computed(function () {
            return self.idpTypesByProtocol[self.protocol()];
        });
        self.idpType = ko.observable('azure_ad');

        self.init = function () {
            self.owner.init();
        };

        return self;
    };

    $(function () {
        var identityProviderHandler = identityProviderModel();
        identityProviderHandler.init();
        $('#ko-new-idp-form').koApplyBindings(identityProviderHandler);
    });
});
