hqDefine("users/js/mobile_workers_main", function() {
    $(function() {
        var mobileWorkersList = hqImport("users/js/mobile_worker_models").mobileWorkersListModel(),
            newMobileWorkersList = hqImport("users/js/mobile_worker_creation_models").newMobileWorkersListModel();
        $("#mobile-workers-list").koApplyBindings(mobileWorkersList);
        $("#new-mobile-workers-list").koApplyBindings(newMobileWorkersList);
        $("#newMobileWorkerModal").koApplyBindings(newMobileWorkersList);
        $("#newMobileWorkerModalTrigger").koApplyBindings(newMobileWorkersList);
    });
});
