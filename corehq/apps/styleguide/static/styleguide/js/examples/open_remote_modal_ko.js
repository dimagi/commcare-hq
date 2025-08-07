import $ from 'jquery';
import ko from 'knockout';
import initialPageData from 'hqwebapp/js/initial_page_data';

$(function () {
    $("#js-ko-demo-open-remote-modal").koApplyBindings(function () {
        return {
            remoteUrl: ko.observable(initialPageData.reverse("styleguide_data_remote_modal") + "?testParam=Okaaaaay"),
        };
    });
});
