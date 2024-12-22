hqDefine('sms/js/chat_contacts', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'datatables.bootstrap',
    'commcarehq',
], function (
    $,
    ko,
    _,
    initialPageData
) {
    var contactListTable = null;

    function filterViewModel() {
        'use strict';
        var self = {};

        self.filterText = ko.observable();

        self.performFilter = function () {
            contactListTable.fnFilter(self.filterText());
        };

        self.clearFilter = function () {
            self.filterText("");
            self.performFilter();
        };
        return self;
    }

    $(function () {
        contactListTable = $("#contact_list").dataTable({
            "aoColumnDefs": [
                {
                    "aTargets": [0],
                    "render": function (data, type, row) {
                        return _.template(
                            '<a target="_blank" href="<%- href %>"><%- content %></a>' +
                            '<span class="btn btn-primary pull-right" ' +
                                  'onClick="window.open(\'<%- url %>\', \'_blank\', \'location=no,menubar=no,scrollbars=no,status=no,toolbar=no,height=400,width=400\');">' +
                            '<%- chat %> <i class="fa fa-share"></i></span>'
                        )({
                            href: row[4],
                            content: row[0],
                            url: row[5],
                            chat: gettext("Chat"),
                        });
                    },
                },
            ],
            "bProcessing": true,
            "bServerSide": true,
            "bSort": false,
            "bFilter": true,
            "oLanguage": {
                "sLengthMenu": gettext("Show ") + "_MENU_" + gettext(" contacts per page"),
                "sProcessing": "<i class='fa fa-spin fa-spinner'></i>" + gettext("Loading Contacts..."),
                "sInfo": gettext("Showing _START_ to _END_ of _TOTAL_ contacts"),
                "sInfoFiltered": gettext("(filtered from _MAX_ total contacts)"),
            },
            "sAjaxSource": initialPageData.reverse("chat_contact_list"),
            "sDom": "lrtip",
        });
        $('#id_filter').koApplyBindings(filterViewModel());
    });
});
