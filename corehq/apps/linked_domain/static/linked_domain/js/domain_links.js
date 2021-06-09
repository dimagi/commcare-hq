hqDefine("linked_domain/js/domain_links", [
    'jquery.rmi/jquery.rmi',
    'hqwebapp/js/initial_page_data',
    'underscore',
    'knockout',
    'hqwebapp/js/alert_user',
    'hqwebapp/js/multiselect_utils',
    'hqwebapp/js/components.ko', // for pagination and search box
    'hqwebapp/js/select2_knockout_bindings.ko',     // selects2 for fields
], function (
    RMI,
    initialPageData,
    _,
    ko,
    alertUser
) {
    var _private = {};
    _private.RMI = function () {};

    var LinkedDataViewModel = function (data) {
        var self = {};
        self.type = data.type;
        self.name = data.name;
        self.lastUpdate = ko.observable(data.last_update);
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
                    self.lastUpdate(data.last_update);
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

        // setup add downstream domain modal view model
        var addDownstreamDomainData = {
            parent: self,
            availableDomains: data.available_domains
        };
        self.addDownstreamDomainViewModel = AddDownstreamDomainViewModel(addDownstreamDomainData);

        // setup pull release content view model
        var pullReleaseContentData = {
            parent: self,
            linkedDataViewModels: _.map(data.model_status, LinkedDataViewModel),
            canUpdate: data.can_update,
            upstreamLink: data.master_link
        };
        self.pullReleaseContentViewModel = PullReleaseContentViewModel(pullReleaseContentData);

        // General data
        self.domain = data.domain;
        self.domain_links = ko.observableArray(_.map(data.linked_domains, DomainLink));

        // Manage Downstream Domains Tab
        // search box
        self.query = ko.observable();
        self.filteredDomainLinks = ko.observableArray([]);
        self.matchesQuery = function (domainLink) {
            return !self.query() || domainLink.linked_domain().toLowerCase().indexOf(self.query().toLowerCase()) !== -1;
        };
        self.filter = function () {
            self.filteredDomainLinks(_.filter(self.domain_links(), self.matchesQuery));
            self.goToPage(1);
        };

        // pagination
        self.paginatedDomainLinks = ko.observableArray([]);
        self.itemsPerPage = ko.observable(5);
        self.totalItems = ko.computed(function () {
            return self.query() ? self.filteredDomainLinks().length : self.domain_links().length;
        });
        self.currentPage = 1;

        self.goToPage = function (page) {
            self.currentPage = page;
            self.paginatedDomainLinks.removeAll();
            var skip = (self.currentPage - 1) * self.itemsPerPage();
            var visibleDomains = self.query() ? self.filteredDomainLinks() : self.domain_links();
            self.paginatedDomainLinks(visibleDomains.slice(skip, skip + self.itemsPerPage()));
        };

        self.onPaginationLoad = function () {
            self.goToPage(1);
        };

        self.deleteLink = function (link) {
            _private.RMI("delete_domain_link", {
                "linked_domain": link.linked_domain(),
            }).done(function () {
                self.domain_links.remove(link);
                var availableDomains = self.addDownstreamDomainViewModel.availableDomains();
                availableDomains.push(link.linked_domain());
                self.addDownstreamDomainViewModel.availableDomains(availableDomains.sort());
                self.goToPage(self.currentPage);
            }).fail(function () {
                alertUser.alert_user(gettext('Something unexpected happened.\n' +
                    'Please try again, or report an issue if the problem persists.'), 'danger');
            });
        };

        // Push Content Tab
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

    var DomainLink = function (link) {
        var self = {};
        self.linked_domain = ko.observable(link.linked_domain);
        self.is_remote = link.is_remote;
        self.master_domain = link.master_domain;
        self.remote_base_url = ko.observable(link.remote_base_url);
        self.lastUpdate = link.last_update;
        if (self.is_remote) {
            self.domain_link = self.linked_domain;
        } else {
            self.domain_link = initialPageData.reverse('domain_links', self.linked_domain());
        }
        return self;
    };

    var PullReleaseContentViewModel = function (data) {
        // Pull Content Tab
        self.parent = data.parent;
        self.linkedDataViewModels = data.linkedDataViewModels;
        self.can_update = data.canUpdate;
        self.upstreamLink = data.upstreamLink;
        if (self.upstreamLink) {
            if (self.upstreamLink.is_remote) {
                self.upstreamURL = self.upstreamLink.master_domain;
            } else {
                self.upstreamURL = initialPageData.reverse('domain_links', self.upstreamLink.master_domain);
            }
        }
        self.upstreamDomain = self.upstreamLink ? self.upstreamLink.master_domain : null;

        // search box
        self.query = ko.observable();
        self.filteredLinkedDataViewModels = ko.observableArray([]);
        self.matchesQuery = function (linkedDataViewModel) {
            return !self.query() || linkedDataViewModel.name.toLowerCase().indexOf(self.query().toLowerCase()) !== -1;
        };
        self.filter = function () {
            self.filteredLinkedDataViewModels(_.filter(self.linkedDataViewModels, self.matchesQuery));
            self.goToPage(1);
        };

        // pagination
        self.paginatedLinkedDataViewModels = ko.observableArray([]);
        self.itemsPerPage = ko.observable(5);
        self.totalItems = ko.computed(function () {
            return self.query() ? self.filteredLinkedDataViewModels().length : self.linkedDataViewModels.length;
        });
        self.currentPage = 1;

        self.goToPage = function (page) {
            self.currentPage = page;
            self.paginatedLinkedDataViewModels.removeAll();
            var skip = (self.currentPage - 1) * self.itemsPerPage();
            var visibleLinkedDataViewModels = self.query() ? self.filteredLinkedDataViewModels() : self.linkedDataViewModels;
            self.paginatedLinkedDataViewModels(visibleLinkedDataViewModels.slice(skip, skip + self.itemsPerPage()));
        };

        self.onPaginationLoad = function () {
            self.goToPage(1);
        };

        return self;
    };

    var AddDownstreamDomainViewModel = function (data) {
        var self = {};
        self.parent = data.parent;
        self.availableDomains = ko.observableArray(data.availableDomains.sort());
        self.value = ko.observable();

        self.addDownstreamDomain = function (viewModel) {
            _private.RMI("create_domain_link", {
                "downstream_domain": viewModel.value(),
            }).done(function (data) {
                self.availableDomains(_.filter(self.availableDomains(), function (item) {
                    return item !== viewModel.value();
                }));
                self.value(null);
                self.parent.domain_links.unshift(DomainLink(data.response));
                self.parent.goToPage(1);
            }).fail(function () {
                alertUser.alert_user(gettext('Unable to link domains.\nPlease try again, or report an issue if the problem persists.'), 'danger');
            });
        };
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
        if ($("#ko-tabs-pull-content").length) {
            $("#ko-tabs-pull-content").koApplyBindings(model.pullReleaseContentViewModel);
        }
        if ($("#ko-tabs-push-content").length) {
            $("#ko-tabs-push-content").koApplyBindings(model);
        }
        if ($("#ko-tabs-manage-downstream").length) {
            $("#ko-tabs-manage-downstream").koApplyBindings(model);
        }

        if ($("#new-downstream-domain-modal").length) {
            $("#new-downstream-domain-modal").koApplyBindings(model.addDownstreamDomainViewModel);
        }

    });
});
