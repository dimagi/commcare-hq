hqDefine('userreports/js/utils', [], function () {

    /**
     * Return an object representing the given DataSourceProperty object
     * in the format expected by the select2 binding.
     * @param {object} dataSourceProperty - A js object representation of a
     *  DataSourceProperty python object.
     * @returns {object} - A js object in the format expected by the select2
     *  knockout binding.
     */
    var convertDataSourcePropertyToSelect2Format = function (dataSourceProperty) {
        return dataSourceProperty;
    };
    /**
     * Return an object representing the given DataSourceProperty object
     * in the format expected by the questionsSelect binding.
     * @param {object} dataSourceProperty - A js object representation of a
     *  DataSourceProperty python object.
     * @returns {object} - A js object in the format expected by the questionsSelect
     *  knockout binding.
     */
    var convertDataSourcePropertyToQuestionsSelectFormat = function (dataSourceProperty) {
        if (dataSourceProperty.type === 'question') {
            return dataSourceProperty.source;
        } else if (dataSourceProperty.type === 'meta') {
            return {
                value: dataSourceProperty.source[0],
                label: dataSourceProperty.text,
                type: dataSourceProperty.type,
            };
        }
    };
    /**
     * Return an object representing the given ColumnOption object in the format
     * expected by the select2 binding.
     * @param {object} columnOption - A js object representation of a
     *  ColumnOption python object.
     * @returns {object} - A js object in the format expected by the select2
     *  knockout binding.
     */
    var convertReportColumnOptionToSelect2Format = function (columnOption) {
        return {
            id: columnOption.id,
            text: columnOption.display,
        };
    };
    /**
     * Return an object representing the given ColumnOption object in the format
     * expected by the questionsSelect binding.
     * @param {object} columnOption - A js object representation of a
     *  ColumnOption python object.
     * @returns {object} - A js object in the format expected by the questionsSelect
     *  knockout binding.
     */
    var convertReportColumnOptionToQuestionsSelectFormat = function (columnOption) {
        var questionSelectRepresentation;
        if (columnOption.question_source) {
            questionSelectRepresentation = Object.assign({}, columnOption.question_source);
        } else {
            questionSelectRepresentation = {
                value: columnOption.id,
                label: columnOption.display,
            };
        }
        questionSelectRepresentation.aggregation_options = columnOption.aggregation_options;
        return questionSelectRepresentation;
    };

    return {
        convertDataSourcePropertyToSelect2Format: convertDataSourcePropertyToSelect2Format,
        convertDataSourcePropertyToQuestionsSelectFormat: convertDataSourcePropertyToQuestionsSelectFormat,
        convertReportColumnOptionToSelect2Format: convertReportColumnOptionToSelect2Format,
        convertReportColumnOptionToQuestionsSelectFormat: convertReportColumnOptionToQuestionsSelectFormat,
    };
});
