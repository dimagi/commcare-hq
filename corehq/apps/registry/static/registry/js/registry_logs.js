hqDefine("registry/js/registry_logs", [
    'moment',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'registry/js/registry_actions',
    'hqwebapp/js/components/pagination',
    'hqwebapp/js/daterangepicker.config',
], function (
    moment,
    ko,
    initialPageData,
    actions,
    pagination
) {
    ko.components.register('pagination', pagination);

    const allDatesText = gettext("Show All Dates"),
        allDomainsText = gettext("All Project Spaces"),
        allActionsText = gettext("All Actions");

    let LogEntryModel = function (data) {
        let self = data;
        self.hrDate = moment(self.date).format("D MMM YYYY HH:mm:ss");
        return self;
    };
    let AuditLogModel = function (registrySlug, projectSpaces, actionTypes) {
        const self = {
            loaded: ko.observable(false),
            total: ko.observable(),
            logs: ko.observableArray([]),
            perPage: ko.observable(),
            loading: ko.observable(false),
            dateRange: ko.observable(allDatesText),
            projectSpaces: [allDomainsText].concat(projectSpaces),
            selectedProjectSpace: ko.observable(allDomainsText),
            currentPage: ko.observable(),
            actionTypes: [allActionsText].concat(actionTypes),
            selectedAction: ko.observable(allActionsText),
        };

        self.load = function () {
            if (self.loaded()) {
                return;
            }
            self.goToPage(1);
        };

        self.filterLogs = function () {
            self.goToPage(1);
        };

        self.goToPage = function (page) {
            self.loading(true);
            const requestData = {
                'page': page,
                'limit': self.perPage(),
            };
            if (self.dateRange() && self.dateRange() !== allDatesText) {
                const separator = $().getDateRangeSeparator(),
                    dates = self.dateRange().split(separator);
                requestData.startDate = dates[0];
                requestData.endDate = dates[1];
            }
            if (self.selectedProjectSpace() && self.selectedProjectSpace() !== allDomainsText) {
                requestData.domain = self.selectedProjectSpace();
            }
            if (self.selectedAction() && self.selectedAction() !== allActionsText) {
                requestData.action = self.selectedAction();
            }
            self.currentPage(page);
            actions.loadLogs(registrySlug, requestData, (data) => {
                self.logs(data.logs.map(LogEntryModel));
                self.total(data.total);
                self.loaded(true);
            }).always(() => {
                self.loading(false);
            });
        };

        return self;
    };

    $(function () {
        $('.report-filter-datespan-filter').each(function (i, el) {
            $(el).createBootstrap3DefaultDateRangePicker();
        });
    });
    return {
        model: AuditLogModel,
    };
});
