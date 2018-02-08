hqDefine("linked_domain/js/domain_links", [
    'jquery.rmi/jquery.rmi',
    'hqwebapp/js/initial_page_data',
    'underscore',
    'knockout',
    'hqwebapp/js/alert_user',
], function(
    RMI,
    initialPageData,
    _,
    ko,
    alert_user,
) {
    var _private = {};
    _private.RMI = function () {};

    var ModelStatus = function(data) {
        var self = this;
        self.type = data.type;
        self.name = data.name;
        self.last_update = ko.observable(data.last_update);
        self.detail = data.detail;
        self.showUpdate = ko.observable(data.can_update);
        self.update_url = null;

        if (self.type === 'app' && self.detail && self.detail.app_id){
            self.update_url = initialPageData.reverse('app_settings', self.detail.app_id)
        }
        self.hasError = ko.observable(false);
        self.hasSuccess = ko.observable(false);
        self.showSpinner = ko.observable(false);

        self.update = function() {
            self.showSpinner(true);
            self.showUpdate(false);
            _private.RMI("update_linked_model", {"model": {
                    'type': self.type,
                    'detail': self.detail
                }}).done(function (data) {
                    self.last_update(data.last_update);
                    self.hasSuccess(true);
                    self.showSpinner(false);
                })
                .fail(function (jqXHR, textStatus, errorThrown) {
                    console.log(errorThrown);
                    self.hasError(true);
                    self.showSpinner(false);
                });
        };
    };

    var DomainLinksViewModel = function(data){
        var self = this;
        self.domain = data.domain;
        self.master_link = data.master_link;
        if (self.master_link) {
            if (self.master_link.is_remote) {
                self.master_href = self.master_link.master_domain;
            } else {
                self.master_href = initialPageData.reverse('domain_links', self.master_link.master_domain);
            }
        }

        self.can_update = data.can_update;
        self.models = data.models;

        self.model_status = _.map(data.model_status, function(model_status) {
            return new ModelStatus(model_status);
        });

        self.linked_domains = ko.observableArray(_.map(data.linked_domains, function(link) {
            return new DomainLink(link);
        }));

        self.deleteLink = function(link) {
            console.log(link);
            _private.RMI("delete_domain_link", {"linked_domain": link.linked_domain()})
                .done(function (data) {
                    self.linked_domains.remove(link);
            })
                .fail(function (jqXHR, textStatus, errorThrown) {
                    console.log(errorThrown);
                    alert_user.alert_user(gettext('Something unexpected happened.\n' +
                        'Please try again, or report an issue if the problem persists.'), 'danger')
            });
        };
    };

    var DomainLink = function (link) {
        var self = this;
        self.linked_domain = ko.observable(link.linked_domain);
        self.is_remote = link.is_remote;
        self.master_domain = link.master_domain;
        self.remote_base_url = ko.observable(link.remote_base_url);
        self.remote_username = ko.observable(link.remote_username);
        self.remote_api_key = ko.observable(link.remote_api_key);
        self.last_update = link.last_update;
        if (self.is_remote){
            self.domain_link = self.linked_domain
        } else{
            self.domain_link = initialPageData.reverse('domain_links', self.linked_domain()   )
        }
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
