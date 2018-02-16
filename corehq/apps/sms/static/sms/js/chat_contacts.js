hqDefine('sms/js/chat_contacts', function() {
var initialPageData = hqImport('hqwebapp/js/initial_page_data');
    var contactListTable = null;

    function FilterViewModel() {
        'use strict';
        var self = this;

        self.filterText = ko.observable();

        self.performFilter = function() {
            contactListTable.fnFilter(self.filterText());
        };

        self.clearFilter = function() {
            self.filterText("");
            self.performFilter();
        };
    }

    $(function(){
        contactListTable = $("#contact_list").dataTable({
            "aoColumnDefs": [
                {
                    "aTargets": [0],
                    "render": function(data, type, row, meta) {
                        return '<a target="_blank" href="'+row[4]+'">'+row[0]+'</a>'+
                               '<span class="btn btn-primary pull-right" '+
                               'onClick="window.open(\''+row[5]+'\', \'_blank\', \'location=no,menubar=no,scrollbars=no,status=no,toolbar=no,height=400,width=400\');">' +
                               gettext("Chat") + '<i class="fa fa-share"></i></span>';
                    }
                }
            ],
            "bProcessing": true,
            "bServerSide": true,
            "bSort": false,
            "bFilter": true,
            "oLanguage": {
                "sLengthMenu": gettext("Show ") + "_MENU_" + gettext(" contacts per page"),
                "sProcessing": '<img src="' + initialPageData.get("ajax_loader") + '" alt="loading indicator" />' + gettext("Loading Contacts..."),
                "sInfo": gettext("Showing _START_ to _END_ of _TOTAL_ contacts"),
                "sInfoFiltered": gettext("(filtered from _MAX_ total contacts)"),
            },
            "sAjaxSource": initialPageData.reverse("chat_contact_list"),
            "sDom": "lrtip",
        });
        var filterViewModel = new FilterViewModel();
        $('#id_filter').koApplyBindings(filterViewModel);
    });
});
