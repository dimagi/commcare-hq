hqDefine("registry/js/registry_logs", [
    'moment',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/alert_user',
    'registry/js/registry_actions',
    'hqwebapp/js/components/pagination'
], function (
    moment,
    ko,
    initialPageData,
    alertUser,
    actions,
    pagination,
) {
    ko.components.register('pagination', pagination);

    let AuditLogModel = function (registrySlug) {
        const self = {
            loaded: ko.observable(false),
            total: ko.observable(),
            logs: ko.observableArray([]),
            perPage: ko.observable(),
            loading: ko.observable(false),
        };

        self.load = function () {
            if (self.loaded()) {
                return;
            }
            self.goToPage(1);
        };


        self.goToPage = function (page) {
            self.loading(true);
            actions.loadLogs(registrySlug, page, self.perPage(), (data) => {
                self.logs(data.logs);
                self.total(data.total);
                self.loaded(true);
            }).always(() => {
                self.loading(false);
            });
        };

        return self;
    }

    return {
        model: AuditLogModel
    }
});
