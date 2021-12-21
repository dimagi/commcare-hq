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
        self.upstreamLink = data.upstream_link ? DomainLink(data.upstream_link) : null;

        // setup getting started view model
        var gettingStartedData = {
            parent: self,
            upstreamDomains: data.upstream_domains,
        };
        self.gettingStartedViewModel = GettingStartedViewModel(gettingStartedData);

        // setup add downstream domain modal view model
        var addDownstreamDomainData = {
            parent: self,
            availableDomains: data.available_domains,
        };
        self.addDownstreamDomainViewModel = AddDownstreamDomainViewModel(addDownstreamDomainData);

        // can only pull content if a link with an upstream domain exists
        var pullContentData = null;
        if (self.upstreamLink) {
            pullContentData = {
                parent: self,
                linkedDataViewModels: _.map(data.view_models_to_pull, LinkedDataViewModel),
                domainLink: self.upstreamLink,
            };
            self.pullContentViewModel = PullContentViewModel(pullContentData);
        }

        // General data
        self.domain = data.domain;
        self.domain_links = ko.observableArray(_.map(data.linked_domains, DomainLink));
        self.showRemoteReports = function () {
            if (data.linkable_ucr) {
                return data.linkable_ucr.length > 0;
            }
            return false;
        };

        self.isUpstreamDomain = ko.computed(function () {
            return self.domain_links().length > 0;
        });
        // doesn't need to be observable because it is impossible to update the existing page to change this property
        self.isDownstreamDomain = data.is_downstream_domain;

        self.isOnlyDownstreamDomain = ko.computed(function () {
            return !self.isUpstreamDomain() && self.isDownstreamDomain;
        });

        // Tab Header Statuses
        self.manageDownstreamDomainsTabStatus = ko.computed(function () {
            return self.isUpstreamDomain() ? "active" : "";
        });

        self.pullContentTabStatus = ko.computed(function () {
            return self.isOnlyDownstreamDomain() ? "active" : "";
        });

        // Tab Content Statuses
        self.manageTabActiveStatus = ko.computed(function () {
            return self.isUpstreamDomain() ? "in active" : "";
        });

        self.pullTabActiveStatus = ko.computed(function () {
            return self.isOnlyDownstreamDomain() ? "in active" : "";
        });

        self.showGetStarted = ko.computed(function () {
            return !self.isUpstreamDomain() && !self.isDownstreamDomain;
        });

        self.showMultipleTabs = ko.computed(function () {
            return self.isUpstreamDomain() || (self.isDownstreamDomain && self.showRemoteReports());
        });


        // can only push content if a link with a downstream domain exists
        var pushContentData = {
            parent: self,
        };
        self.pushContentViewModel = PushContentViewModel(pushContentData);
        // Manage Downstream Domains Tab
        // search box
        self.query = ko.observable();
        self.filteredDomainLinks = ko.observableArray([]);
        self.matchesQuery = function (domainLink) {
            return !self.query() || domainLink.downstreamDomain().toLowerCase().indexOf(self.query().toLowerCase()) !== -1;
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

        self.linkableUcr = ko.observableArray(_.map(data.linkable_ucr, function (report) {
            return RemoteLinkableReport(report, self.upstreamLink);
        }));

        self.createRemoteReportLink = function (reportId) {
            _private.RMI("create_remote_report_link", {
                "master_domain": self.upstreamLink.upstreamDomain,
                "linked_domain": self.upstreamLink.downstreamDomain(),
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
                "linked_domain": link.downstreamDomain(),
            }).done(function () {
                self.domain_links.remove(link);
                var availableDomains = self.addDownstreamDomainViewModel.availableDomains();
                availableDomains.push(link.downstreamDomain());
                self.addDownstreamDomainViewModel.availableDomains(availableDomains.sort());
                self.goToPage(self.currentPage);
            }).fail(function () {
                alertUser.alert_user(gettext('Something unexpected happened.\n' +
                    'Please try again, or report an issue if the problem persists.'), 'danger');
            }).always(function () {
                // fix for b3
                $('body').removeClass('modal-open');
                var $modalBackdrop = $('.modal-backdrop');
                if ($modalBackdrop) {
                    $modalBackdrop.remove();
                }
            });
        };

        return self;
    };

    var DomainLink = function (link) {
        var self = {};
        self.downstreamDomain = ko.observable(link.downstream_domain);
        self.isRemote = link.is_remote;
        self.upstreamDomain = link.upstream_domain;
        self.lastUpdate = link.last_update;
        self.upstreamUrl = link.upstream_url;
        self.downstreamUrl = link.downstream_url;
        return self;
    };

    var PushContentViewModel = function (data) {
        var self = {};
        self.parent = data.parent;
        self.domainsToPush = ko.observableArray();
        self.modelsToPush = ko.observableArray();
        self.buildAppsOnPush = ko.observable(false);
        self.pushInProgress = ko.observable(false);
        self.enablePushButton = ko.computed(function () {
            return self.domainsToPush().length && self.modelsToPush().length && !self.pushInProgress();
        });

        self.localDownstreamDomains = ko.computed(function () {
            return self.parent.domain_links().reduce(function (result, link) {
                if (!link.isRemote) {
                    return result.concat(link.downstreamDomain());
                }
                return result;
            }, []);
        });

        self.domainMultiselect = {
            selectableHeaderTitle: gettext("All project spaces"),
            selectedHeaderTitle: gettext("Project spaces to push to"),
            searchItemTitle: gettext("Search project spaces"),
            options: self.localDownstreamDomains,
        };

        self.canPush = ko.computed(function () {
            return self.localDownstreamDomains().length > 0;
        });

        self.pushContent = function () {
            self.pushInProgress(true);
            _private.RMI("create_release", {
                models: _.map(self.modelsToPush(), JSON.parse),
                linked_domains: self.domainsToPush(),
                build_apps: self.buildAppsOnPush(),
            }).done(function (data) {
                alertUser.alert_user(data.message, data.success ? 'success' : 'danger');
                self.pushInProgress(false);
            }).fail(function () {
                alertUser.alert_user(gettext('Something unexpected happened.\nPlease try again, or report an issue if the problem persists.'), 'danger');
                self.pushInProgress(false);
            });
        };

        return self;
    };

    var PullContentViewModel = function (data) {
        var self = {};
        self.parent = data.parent;
        self.linkedDataViewModels = data.linkedDataViewModels;
        self.domainLink = data.domainLink;

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

    var RemoteLinkableReport = function (report, upstreamLink) {
        var self = {};
        self.id = report.id;
        self.title = report.title;
        self.alreadyLinked = ko.observable(report.already_linked);

        self.createLink = function () {
            _private.RMI("create_remote_report_link", {
                "master_domain": upstreamLink.upstreamDomain,
                "linked_domain": upstreamLink.downstreamDomain(),
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

    var AddDownstreamDomainViewModel = function (data) {
        var self = {};
        self.parent = data.parent;
        self.availableDomains = ko.observableArray(data.availableDomains.sort());
        self.domainToAdd = ko.observable();
        self.didSelectDomain = ko.computed(function () {
            return self.domainToAdd() !== null && self.domainToAdd() !== undefined;
        });

        self.addDownstreamDomain = function (viewModel) {
            _private.RMI("create_domain_link", {
                "downstream_domain": viewModel.domainToAdd(),
            }).done(function (response) {
                if (response.success) {
                    self.availableDomains(_.filter(self.availableDomains(), function (item) {
                        return item !== viewModel.domainToAdd();
                    }));
                    self.parent.domain_links.unshift(DomainLink(response.domain_link));
                    self.parent.goToPage(1);
                } else {
                    var errorMessage = _.template(
                        gettext('Unable to link project spaces. <%- error %>')
                    )({error: response.message});
                    alertUser.alert_user(errorMessage, 'danger');
                }
                self.domainToAdd(null);
            }).fail(function () {
                alertUser.alert_user(gettext('Unable to link project spaces.\nPlease try again, or report an issue if the problem persists.'), 'danger');
            });
        };
        return self;
    };

    var GettingStartedViewModel = function (data) {
        var self = {};
        self.parent = data.parent;
        var sortedUpstreamDomains = data.upstreamDomains.sort(function (first, second) {
            var firstName = first.name.toUpperCase();
            var secondName = second.name.toUpperCase();
            if (firstName > secondName) {
                return 1;
            } else if (firstName < secondName) {
                return -1;
            } else {
                return 0;
            }
        });
        self.upstreamDomains = ko.observableArray(sortedUpstreamDomains);

        self.upstreamButtonClass = ko.computed(function () {
            return self.upstreamDomains().length > 0 ? "btn-default" : "btn-primary";
        });

        self.goToUpstream = function (data) {
            window.location.href = data.upstreamDomains()[0].url;
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
        $("#ko-linked-projects").koApplyBindings(model);

        if ($("#new-downstream-domain-modal").length) {
            $("#new-downstream-domain-modal").koApplyBindings(model.addDownstreamDomainViewModel);
        }

    });
});
