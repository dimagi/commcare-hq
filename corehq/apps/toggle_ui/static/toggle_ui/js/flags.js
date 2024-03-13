hqDefine('toggle_ui/js/flags', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/bootstrap3/alert_user',
    'reports/js/config.dataTables.bootstrap',
    'hqwebapp/js/bootstrap3/components.ko',    // select toggle widget
], function (
    $,
    ko,
    _,
    alertUser,
    datatablesConfig
) {
    var dataTableElem = '.datatable';
    let buildViewModel = function () {
        let self = {};
        self.tagFilter = ko.observable(null);
        self.downloadPollUrl = ko.observable(null);
        self.downloadPollId = ko.observable(null);
        self.downloadContent = ko.observable(null);

        self.downloadFile = function () {
            self.downloadPollUrl(null);
            self.downloadPollId(null);
            self.downloadContent(null);

            let appliedFilter = self.tagFilter();
            if (appliedFilter === "all") {
                appliedFilter = '';
            }
            $.post({
                url: "export_toggles/",
                data: {"tag": appliedFilter},
                success: function (data) {
                    self.downloadPollUrl(data.download_url);
                    self.downloadPollId(data.download_id);
                    self.pollDownloadStatus();
                },
                error: function (resp) {
                    self.downloadPollUrl(null);
                    self.downloadPollId(null);
                    self.downloadContent(null);
                    alertUser.alert_user(resp.responseText);
                },
            });
        };

        self.pollDownloadStatus = function () {
            if (viewModel.downloadPollUrl()) {
                $.ajax({
                    url: viewModel.downloadPollUrl(),
                    success: function (resp) {
                        self.downloadContent(resp);
                        if (!self.isDone(resp)) {
                            setTimeout(self.pollDownloadStatus, 1500);
                        } else {
                            self.downloadPollUrl(null);
                            self.downloadPollId(null);
                        }
                    },
                    error: function (resp) {
                        alertUser.alert_user(resp.responseText);
                    },
                });
            }
        };

        self.isDone = function (progressResponse) {
            var readyId = 'ready_' + self.downloadPollId(),
                errorId = 'error_' + self.downloadPollId();
            return progressResponse &&
                progressResponse.trim().length &&
                _.any([readyId, errorId], function (elid) {
                    return progressResponse.indexOf(elid) >= 0;
                });
        };
        return self;
    };

    let viewModel = buildViewModel();
    $.fn.dataTableExt.afnFiltering.push(
        function (oSettings, aData) {
            if (viewModel.tagFilter() === 'all') {
                return true;
            }
            var tag = aData[0].replace(/\s+/g," ").replace(/<.*?>/g, "").replace(/^\d+ /, "");
            if (viewModel.tagFilter() === "Solutions" && tag.includes("Solutions")) {
                return true;
            }
            return tag === viewModel.tagFilter();
        }
    );
    $('#feature_flags').koApplyBindings(viewModel);
    var table = datatablesConfig.HQReportDataTables({
        dataTableElem: dataTableElem,
        showAllRowsOption: true,
        includeFilter: true,
    });
    table.render();

    viewModel.tagFilter.subscribe(function () {
        table.datatable.fnDraw();
    });
});
