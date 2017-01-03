/* global jQuery */
hqDefine('reports/js/reports.util.js', function () {
    return {
        urlSerialize: function (filters, exclude) {
            exclude = exclude || [];
            // pulled chiefly from the jquery serialize and serializeArray functions
            var rCRLF = /\r?\n/g,
                rinput = /^(?:color|date|datetime|email|hidden|month|number|password|range|search|tel|text|time|url|week)$/i,
                rselectTextarea = /^(?:select|textarea)/i;
            return jQuery.param($(filters).map(function () {
                return this.elements ? jQuery.makeArray(this.elements) : this;
            })
            .filter(function (i, elem) {
                return (
                    this.name &&
                    !this.disabled &&
                    (this.checked || rselectTextarea.test(this.nodeName) || rinput.test(this.type)) &&
                    exclude.indexOf(elem.name) === -1
                );
            })
            .map(function (i, elem) {
                var val = jQuery(this).val();
                if (val === null) {
                    return null;
                }
                if (elem.getAttribute('data-ajax-select2')) {
                    val = val.split(',');
                }
                return jQuery.isArray(val) ?
                    jQuery.map(val, function (val) {
                        return {
                            name: elem.name,
                            value: val.replace(rCRLF, "\r\n"),
                        };
                    }) :
                {name: elem.name, value: val.replace(rCRLF, "\r\n")};
            }).get(), true);
        },
    };
});

