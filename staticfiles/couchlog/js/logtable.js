function init_log_table(filter, id_column, archived_column, date_column,
                        message_column, actions_column, email_column, no_cols,
                        show, ajax_url) 
{
    var not_sortable = [];
    for (i=0; i<no_cols; i++) {
        if (i!= date_column) {
            not_sortable.push(i);
        }
    }
        
    $('.datatable').dataTable({
        "bProcessing": true,
        "bServerSide": true,
        "bFilter": filter,
        "bJQueryUI": true, 
        "sAjaxSource": ajax_url,
        "aaSorting": [[ date_column, "desc" ]],
        "fnRowCallback": function( nRow, aData, iDisplayIndex ) {
            // annotate row with id
            $(nRow).attr("id", aData[id_column]);
            
            // annotate row with class
            if (aData[archived_column] == "true") {
               $(nRow).addClass("archived");
            } else {
               $(nRow).addClass("inbox");
            }
            
            // remove added odd/even styles.  they mess with our custom classes
            // eh, this isn't so bad actually
            // $(nRow).removeClass("odd even");
            return nRow;
        },
        "fnServerData": function ( sSource, aoData, fnCallback ) {
            // add data to the post
            // are we in the inbox or all view
            aoData.push( { "name": "show", "value": show} );
            
            // previous startkey, endkeys if any.
            // currently unused but may one day be necessary for paging                   
            aoData.push( { "name": "startkey", "value": $("#startkey").val() } );
            aoData.push( { "name": "endkey", "value": $("#endkey").val() } );
            
            $.getJSON( sSource, aoData, function(json) {
               // set startkey and endkey in their appropriate divs, these are
               // currently unused but may one day be necessary for paging                 
               $("#startkey").val(JSON.stringify(json.startkey));
               $("#endkey").val(JSON.stringify(json.endkey));
               fnCallback(json);
            });
        },
        "aoColumnDefs": [ 
                {
                    "fnRender": function ( oObj ) {
                        if (!oObj.aData[message_column]) {
                            display = "UNKNOWN ERROR";
                        } else {
                            display = oObj.aData[message_column];
                        }
                        return '<a href="/couchlog/ajax/single/' + oObj.aData[0] + '" onclick="$(\'#modal-placeholder\').jqmShow($(this)); return false;"  class="logview">' + display +'</a>';
                    },
                    "aTargets": [message_column]
                }, 
                {
                    "fnRender": function ( oObj ) {
                        return '<a href="#" class="emaillink">report error</a>';
                    },
                    "aTargets": [ email_column ]
                }, 
                {
                    "fnRender": function ( oObj ) {
                        is_archived = oObj.aData[archived_column] === false;
                        del_html = '<input type="button" class="updatebutton" action_type="delete" value="delete" />';
                        if (is_archived) {
                            arch_html = '<input type="button" class="updatebutton" action_type="archive" value="archive" />';
                        } else {
                            arch_html = '<input type="button" class="updatebutton" action_type="move_to_inbox" value="move to inbox" />';
                        }
                        return arch_html + del_html;
                    },
                    "aTargets": [ actions_column ]
                }, 
                { "bVisible": false,  "aTargets": [ id_column, archived_column ] },
                { "bSortable": false, "aTargets": not_sortable},
                //{ "bSortable": true, "aTargets": sortable}, 
                { "sWidth": "11em", "aTargets": [ date_column ] },
                { "sWidth": "7em", "aTargets": [ email_column ] },
                { "sWidth": "11em", "aTargets": [ actions_column ] }
        ]
    });
}