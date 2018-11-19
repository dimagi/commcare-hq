(function() {
    // Create the connector object
    var myConnector = tableau.makeConnector();

    // Define the schema
    myConnector.getSchema = function(schemaCallback) {
        var cols = [{
            id: "id",
            dataType: tableau.dataTypeEnum.string
        }, {
            id: "name",
            dataType: tableau.dataTypeEnum.string
        }, {
            id: "abc",
            dataType: tableau.dataTypeEnum.string
        }];

        var tableSchema = {
            id: "cases",
            alias: "Case List",
            columns: cols
        };

        schemaCallback([tableSchema]);
    };

    myConnector.init = function(initCallback) {
        tableau.authType = tableau.authTypeEnum.none;
        initCallback();
    }

    // Download the data
    myConnector.getData = function(table, doneCallback) {
        $.getJSON("http://localhost:8000/hq/admin/4.5_week.geojson", function(resp) {
            var cases = resp.cases,
                tableData = [];

            // Iterate over the JSON object
            for (var i = 0, len = cases.length; i < len; i++) {
                tableData.push({
                    "id": cases[i].id,
                    "name": cases[i].name,
                    "abc": cases[i]['properties'].abc
                });
            }

            table.appendRows(tableData);
            doneCallback();
        });
    };

    tableau.registerConnector(myConnector);

    // Create event listeners for when the user submits the form
    $(document).ready(function() {
        $("#submitButton").click(function() {
            tableau.connectionName = "USGS Earthquake Feed"; // This will be the data source name in Tableau
            tableau.submit(); // This sends the connector object to Tableau
        });
    });
})();
