hqDefine("linked_domain/js/domain_links", [
    'jquery.rmi/jquery.rmi',
    'hqwebapp/js/initial_page_data',
    'underscore',
    'knockout',
    'hqwebapp/js/alert_user',
    'hqwebapp/js/multiselect_utils',
], function (
    RMI,
    initialPageData,
    _,
    ko,
    alertUser
) {
    var _private = {};
    _private.RMI = function () {};

    var ModelStatus = function (data) {
        var self = {};
        self.type = data.type;
        self.name = data.name;
        self.last_update = ko.observable(data.last_update);
        self.detail = data.detail;
        self.showUpdate = ko.observable(data.can_update);
        self.update_url = null;

        if (self.type === 'app' && self.detail && self.detail.app_id) {
            self.update_url = initialPageData.reverse('app_settings', self.detail.app_id);
        }
        self.error = ko.observable("");
        self.hasSuccess = ko.observable(false);
        self.showSpinner = ko.observable(false);

        self.update = function () {
            self.showSpinner(true);
            self.showUpdate(false);
            _private.RMI("update_linked_model", {"model": {
                'type': self.type,
                'detail': self.detail,
            }}).done(function (data) {
                if (data.error) {
                    self.error(data.error);
                } else {
                    self.last_update(data.last_update);
                    self.hasSuccess(true);
                }
                self.showSpinner(false);
            }).fail(function () {
                self.error(gettext("Error updating."));
                self.showSpinner(false);
            });
        };

        return self;
    };

    var DomainLinksViewModel = function (data) {
        var self = {};
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

        self.model_status = _.map(data.model_status, ModelStatus);

        self.linked_domains = ko.observableArray(_.map(data.linked_domains, function (link) {
            return DomainLink(link);
        }));

        self.linkableUcr = ko.observableArray(_.map(data.linkable_ucr, function (report) {
            return RemoteLinkableReport(report, self.master_link);
        }));
        self.createRemoteReportLink = function (reportId) {
            _private.RMI("create_remote_report_link", {
                "master_domain": self.master_link.master_domain,
                "linked_domain": self.master_link.linked_domain,
                "report_id": reportId,
            }).done(function (data) {
                if (data.success) {
                    alertUser.alert_user(gettext('Report successfully linked.'), 'success');
                } else {
                    alertUser.alert_user(gettext(
                        'Something unexpected happened.\n' +
                        'Please try again, or report an issue if the problem persists.'), 'danger');
                }
            }).fail(function () {
                alertUser.alert_user(gettext(
                    'Something unexpected happened.\n' +
                    'Please try again, or report an issue if the problem persists.'), 'danger');
            });
        };

        self.deleteLink = function (link) {
            _private.RMI("delete_domain_link", {
                "linked_domain": link.linked_domain(),
            }).done(function () {
                self.linked_domains.remove(link);
            }).fail(function () {
                alertUser.alert_user(gettext('Something unexpected happened.\n' +
                    'Please try again, or report an issue if the problem persists.'), 'danger');
            });
        };

        self.domainsToRelease = ko.observableArray();
        self.modelsToRelease = ko.observableArray();
        self.buildAppsOnRelease = ko.observable(false);
        self.releaseInProgress = ko.observable(false);
        self.enableReleaseButton = ko.computed(function () {
            return self.domainsToRelease().length && self.modelsToRelease().length && !self.releaseInProgress();
        });
        self.createRelease = function () {
            self.releaseInProgress(true);
            _private.RMI("create_release", {
                models: _.map(self.modelsToRelease(), JSON.parse),
                linked_domains: self.domainsToRelease(),
                build_apps: self.buildAppsOnRelease(),
            }).done(function (data) {
                alertUser.alert_user(data.message, data.success ? 'success' : 'danger');
                self.releaseInProgress(false);
            }).fail(function () {
                alertUser.alert_user(gettext('Something unexpected happened.\nPlease try again, or report an issue if the problem persists.'), 'danger');
                self.releaseInProgress(false);
            });
        };

        return self;
    };

    var RemoteLinkableReport = function (report, masterLink) {
        var self = {};
        self.id = report.id;
        self.title = report.title;
        self.alreadyLinked = ko.observable(report.already_linked);

        self.createLink = function () {
            _private.RMI("create_remote_report_link", {
                "master_domain": masterLink.master_domain,
                "linked_domain": masterLink.linked_domain,
                "report_id": self.id,
            }).done(function (data) {
                if (data.success) {
                    alertUser.alert_user(gettext('Report successfully linked.'), 'success');
                    self.alreadyLinked(true);
                } else {
                    alertUser.alert_user(gettext(
                        'Something unexpected happened.\n' +
                            'Please try again, or report an issue if the problem persists.'), 'danger');
                }
            }).fail(function () {
                alertUser.alert_user(gettext(
                    'Something unexpected happened.\n' +
                        'Please try again, or report an issue if the problem persists.'), 'danger');
            });
        };

        return self;
    };

    var DomainLink = function (link) {
        var self = {};
        self.linked_domain = ko.observable(link.linked_domain);
        self.is_remote = link.is_remote;
        self.master_domain = link.master_domain;
        self.remote_base_url = ko.observable(link.remote_base_url);
        self.last_update = link.last_update;
        if (self.is_remote) {
            self.domain_link = self.linked_domain;
        } else {
            self.domain_link = initialPageData.reverse('domain_links', self.linked_domain());
        }
        return self;
    };

    var setRMI = function (rmiUrl, csrfToken) {
        var _rmi = RMI(rmiUrl, csrfToken);
        _private.RMI = function (remoteMethod, data) {
            return _rmi("", data, {headers: {"DjNg-Remote-Method": remoteMethod}});
        };
    };

    $(function () {
        var view_data = initialPageData.get('view_data');
        var csrfToken = $("#csrfTokenContainer").val();
        setRMI(initialPageData.reverse('linked_domain:domain_link_rmi'), csrfToken);

        var model = DomainLinksViewModel(view_data);
        $("#domain_links").koApplyBindings(model);
    });
});
