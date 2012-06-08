jQuery.prototype.langcodes = function() {
    return this.autocomplete({
        source: function( request, response ) {
            $.ajax({
                url: "/langcodes/langs.json",
                data: request,
                dataType: 'json',
                success: function( data ) {
                    response($.map( data, function( item ) {
                        return {
                            label: item.code + " (" + item.name + ") ",
                            value: item.code
                        }
                    }));
                }
            });
        },
        minLength: 0
    });
}