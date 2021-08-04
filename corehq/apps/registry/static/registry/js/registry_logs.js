hqDefine("registry/js/registry_logs", [
    'moment',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/alert_user',
    'registry/js/registry_actions',
], function (
    moment,
    ko,
    initialPageData,
    alertUser,
    actions,
) {
    let AuditLogModel = function (registrySlug) {
        const self = {
            loaded: ko.observable(false),
            total: ko.observable(),
            logs: ko.observableArray([])
        };

        self.load = function () {
            if (self.loaded()) {
                return;
            }
            actions.loadLogs(registrySlug, (data) => {
                self.logs(data.logs);
                self.total(data.total);
                self.loaded(true);
            })
        }

        return self;
    }

    return {
        model: AuditLogModel
    }
});
