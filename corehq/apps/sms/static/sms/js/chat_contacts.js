hqDefine('sms/js/chat_contacts', function() {
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
                               'onClick="window.open(\''+row[5]+'\', \'_blank\', \'location=no,menubar=no,scrollbars=no,status=no,toolbar=no,height=400,width=400\');">'+
                               '{% trans "Chat" %} <i class="fa fa-share"></i></span>';
                    }
                }
            ],
            "bProcessing": true,
            "bServerSide": true,
            "bSort": false,
            "bFilter": true,
            "oLanguage": {
                "sLengthMenu": "{% trans "Show" %} _MENU_ {% trans "contacts per page" %}",
                "sProcessing": '<img src="{% static "hqwebapp/images/ajax-loader.gif" %}" alt="loading indicator" /> {% trans "Loading Contacts..." %}',
                "sInfo": "{% trans "Showing _START_ to _END_ of _TOTAL_ contacts" %}",
                "sInfoFiltered": "{% trans "(filtered from _MAX_ total contacts)" %}",
            },
            "sAjaxSource": "{% url "chat_contact_list" domain %}",
            "sDom": "lrtip",
        });
        var filterViewModel = new FilterViewModel();
        $('#id_filter').koApplyBindings(filterViewModel);
    });
});
