(function (angular, undefined) {
    'use strict';
    // module: hq.dashboard
    var dashboard = angular.module('hq.dashboard', []);
    /* All the components necessary to provide a functional, modular dashboard
    for a returning user.
     */
    dashboard.constant('dashboardConfig', {
        staticRoot: '/'
    });

    var utils = {
        getTemplate: function (config, filename) {
            return config.staticRoot + 'dashboard/ng_partials/' + filename;
        }
    };

    var dashboardControllers = {};
    dashboardControllers.PaginatedTileController = function ($scope, djangoRMI) {
        var self = this;

        $scope.paginatedItems = [];
        $scope.isLoading = false;
        $scope.limit = 5;
        $scope.total = 0;
        $scope.maxSize = 8;
        $scope.default = {};

        self.retries = 0;

        self.init = function (attrs) {
            $scope.slug = attrs.slug;
            $scope.title = attrs.title;
            $scope.setPage(1);
        };

        $scope.setPage = function (pageNo) {
            $scope.currentPage = pageNo;
            self.refresh();
        };

        $scope.pageChanged = function () {
            self.refresh();
        };

        $scope.paginationIsActive = function () {
            return $scope.total > $scope.limit;
        };

        $scope.showSpinner = function () {
            return !!$scope.isLoading;
        };

        $scope.showItemList = function () {
            return !$scope.isLoading && $scope.total > 0;
        };

        $scope.showDefault = function () {
            return $scope.total === 0 && $scope.default.show;
        };

        self.refresh = function () {
            $scope.isLoading = true;
            djangoRMI.update_tile(self.getPaginationContext())
                .success(self.setPaginationContext).error(self.retry);
        };

        self.getPaginationContext = function () {
            return {
                pagination: {
                    total: $scope.total,
                    limit: $scope.limit,
                    currentPage: $scope.currentPage
                },
                paginatedItems: $scope.paginatedItems,
                slug: $scope.slug
            }
        };

        self.setPaginationContext = function (data) {
            var resp = data.response.pagination;
            $scope.total = resp.total;
            $scope.currentPage = resp.currentPage;
            $scope.itemsPerPage = resp.limit;
            $scope.paginatedItems = resp.paginatedItems || [];
            $scope.isLoading = false;
            $scope.default = data.response.default || {};
            $scope.helpText = data.response.helpText;
        };

        self.retry = function () {
            self.retries ++;
            if (self.retries <= 10) {
                self.refresh();
            } else {
                $scope.isLoading = false;
            }
        };
    };

    dashboardControllers.IconTileController = function ($scope, djangoRMI) {
        var self = this;

        $scope.icon = '';
        $scope.url = '';
        $scope.isExternal = false;
        $scope.helpText = '';

        self.retries = 0;

        self.init = function (attrs) {
            $scope.title = attrs.title;
            $scope.slug = attrs.slug;
            self.refreshIcon();
        };

        self.refreshIcon = function () {
            djangoRMI.update_tile({
                slug: $scope.slug
            }).success(self.updateIcon).error(self.retry);
        };

        self.updateIcon = function (data) {
            if (data.success) {
                $scope.icon = data.response.icon;
                $scope.url = data.response.url;
                $scope.isExternal = !!data.response.isExternal;
                $scope.helpText = data.response.helpText;
                if ($scope.isExternal) {
                    $($scope.externalLink).attr('target', '_blank');
                }
            }
        };

        self.retry = function () {
            self.retries ++;
            if (self.retries <= 10) {
                self.refreshIcon();
            }
        };
    };

    dashboardControllers.permissionsController = function ($scope, djangoRMI) {
        var self = this;

        self.retries = 0;

        self.checkPermissions = function (slug) {
            djangoRMI.check_permissions({
                slug: slug
            }).success(self.updatePermissions).error(self.retry);
        };

        self.updatePermissions = function (data) {
            $scope.hasPermissions = data.hasPermissions;
        };

        self.retry = function () {
            self.retries ++;
            if (self.retries <= 10) {
                self.checkPermissions($scope.slug);
            }
        };
    };


    var dashboardDirectives = {};

    dashboardDirectives.paginatedTileDirective = function (dashboardConfig) {
        var link = function ($scope, element, attrs, controller) {
            controller.init(attrs);
        };

        return {
            scope: true,
            restrict: 'EA',
            templateUrl: utils.getTemplate(dashboardConfig, 'paginated_tile.html'),
            controller: dashboardControllers.PaginatedTileController,
            link: link
        };
    };

    dashboardDirectives.iconTileDirective = function (dashboardConfig) {
        var link = function ($scope, element, attrs, controller) {
            controller.init(attrs);
        };

        return {
            scope: true,
            restrict: 'EA',
            templateUrl: utils.getTemplate(dashboardConfig, 'icon_tile.html'),
            controller: dashboardControllers.IconTileController,
            link: link
        };
    };

    dashboardDirectives.externalLinkDirective = function () {
        var link = function ($scope, element) {
            if (typeof($scope.isExternal) !== 'undefined') {
                $scope.externalLink = element;
            }
        };

        return {
            restrict: 'A',
            link: link
        };
    };

    dashboardDirectives.trackAnalyticsDirective = function () {
        // todo
        var link = function ($scope, element, attrs) {
        };

        return {
            restrict: 'A',
            link: link
        };
    };

    dashboardDirectives.checkPermissionsDirective = function () {
        var link = function ($scope, element, attrs, controller) {
            controller.checkPermissions($scope.slug);
        };

        return {
            restrict: 'A',
            controller: dashboardControllers.permissionsController,
            link: link
        };
    };

    dashboard.controller(dashboardControllers);
    dashboard.directive('tilePaginate', dashboardDirectives.paginatedTileDirective);
    dashboard.directive('tileIcon', dashboardDirectives.iconTileDirective);
    dashboard.directive('processExternalLink', dashboardDirectives.externalLinkDirective);
    dashboard.directive('trackAnalytics', dashboardDirectives.trackAnalyticsDirective);
    dashboard.directive('checkPermissions', dashboardDirectives.checkPermissionsDirective);

}(window.angular));

