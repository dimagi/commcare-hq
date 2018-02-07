hqDefine("linked_domain/js/domain_links", [
    'jquery.rmi/jquery.rmi',
    'hqwebapp/js/initial_page_data',
    'underscore',
    'knockout',
], function(
    RMI,
    initialPageData,
    _,
    ko,
) {
    var _private = {};
    _private.RMI = function () {};

    var ModelStatus = function(data) {
        var self = this;
        self.type = data.type;
        self.name = data.name;
        self.last_update = ko.observable(data.last_update);
        self.detail = data.detail;
        self.can_update = data.can_update;
        self.update_url = null;

        if (self.type === 'app' && self.detail && self.detail.app_id){
            self.update_url = initialPageData.reverse('app_settings', self.detail.app_id)
        }
        self.hasError = ko.observable(false);

        self.update = function() {
            _private.RMI("update_linked_model", {"model": {
                    'type': self.type,
                    'detail': self.detail
                }}).done(function (data) {
                    self.last_update(data.last_update);
                })
                .fail(function (jqXHR, textStatus, errorThrown) {
                    console.log(errorThrown);
                    self.hasError(true);
                });
        };
    };

    var DomainLinksViewModel = function(data){
        var self = this;
        self.master_link = data.master_link;
        self.linked_domains = data.linked_domains;
        self.can_update = data.can_update;
        self.models = data.models;

        self.model_status = _.map(data.model_status, function(model_status) {
            return new ModelStatus(model_status);
        });

        console.log(self.model_status)
    };

    var setRMI = function (rmiUrl, csrfToken) {
        var _rmi = RMI(rmiUrl, csrfToken);
        _private.RMI = function (remoteMethod, data) {
            return _rmi("", data, {headers: {"DjNg-Remote-Method": remoteMethod}});
        };
    };


    $(function() {
        var view_data = initialPageData.get('view_data');
        var csrfToken = $("#csrfTokenContainer").val();
        setRMI(initialPageData.reverse('linked_domain:domain_link_rmi'), csrfToken);
        $("#domain_links").koApplyBindings(new DomainLinksViewModel(view_data));
    });
});
