hqDefine('userreports/js/constants.js', function () {
    var COUNT_PER_CHOICE = "Count per Choice";
    var SUM = "Sum";
    return {
        FORMAT_OPTIONS: ["Choice", "Date"],
        DEFAULT_FILTER_FORMAT_OPTIONS: ["Value", "Date"],
        COUNT_PER_CHOICE: COUNT_PER_CHOICE,
        SUM: SUM,
        DEFAULT_CALCULATION_OPTIONS: ["Group By", COUNT_PER_CHOICE, SUM, "Average"],
    };
});
