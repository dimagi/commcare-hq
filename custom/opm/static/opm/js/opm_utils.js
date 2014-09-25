var SEPARATOR_DIV = '<div style="page-break-after: always; margin:0; padding:0; border: none;"></div>';

function splitTable(table, maxHeight) {
    var header = table.children("thead");
    if (!header.length)
        return;

    var headerHeight = header.outerHeight();
    var header = header.detach();

    var splitIndices = [0];
    var rows = table.children("tbody").children();

    maxHeight -= headerHeight;
    var currHeight = 0;
    rows.each(function(i, row) {
        currHeight += $(rows[i]).outerHeight();
        if (currHeight > maxHeight) {
            splitIndices.push(i);
            currHeight = $(rows[i]).outerHeight();
        }
    });
    splitIndices.push(undefined);

    table = table.replaceWith('<div id="_split_table_wrapper"></div>');
    table.empty();

    for(var i=0; i<splitIndices.length-1; i++) {
        var newTable = table.clone();
        header.clone().appendTo(newTable);
        $('<tbody />').appendTo(newTable);
        rows.slice(splitIndices[i], splitIndices[i+1]).appendTo(newTable.children('tbody'));
        newTable.appendTo("#_split_table_wrapper");
        if (splitIndices[i+1] !== undefined) {
            $(SEPARATOR_DIV).appendTo("#_split_table_wrapper");
        }
    }
}

function split($table, chunkSize) {
    var cols = $("th", $table).length - 1;
    var n = cols / chunkSize;

    var $newTable = $table.clone()
    $table.after($newTable);
    $table.after($(SEPARATOR_DIV))
    for (var i = chunkSize; i > 0; i--) {
        $('td:nth-child('+i+'),th:nth-child('+i+')', $newTable).remove();
    }
    for (var i = cols; i > chunkSize; i--) {
        $('td:nth-child('+i+'),th:nth-child('+i+')', $table).remove();
    }
}