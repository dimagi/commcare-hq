jQuery(document).ready(function($) {
    // courtesy of http://colorbrewer2.org/
    var COUNTRY_COLORS = ['#fef0d9','#fdcc8a','#fc8d59','#e34a33','#b30000'];

    function colorAll() {
        if (countriesGeo !== undefined) {
            countriesGeo.setStyle(style);
            map.removeControl(legend);
            legend.addTo(map);
        }
    }

    var dataController = function() {
        var that = {};

        // { countryName : { projectName : { propertyName: propertyValue } } }
        var projectsByCountryThenName = {};
        var maxNumProjects = 0;
        
        that.refreshProjectData = function (filter) {
            // todo: use filters to filter ES search query
            $.ajax({
                url: 'http://localhost:8000/hq/admin/json/project_map/',
                dataType: 'json',
                success: function (data) {
                    var tempProjects = {};
                    // data.aaData seems to hold the information. not sure though if this is the best way of getting the data. hmm.
                    data.aaData.forEach(function (project) {
                        var countryNamesIndex = 5;
                        // todo: figure out a better thing to do about mismatch between country NAMES and Names
                        if (project[countryNamesIndex].length < 1) {
                            //todo: deal with no listed deployment country. just ignore??
                        } else {
                            // this will use only the first listed country
                            var countryName = project[countryNamesIndex][0].toLowerCase();
                            console.log(project[countryNamesIndex]);
                            if (!tempProjects[countryName]) {
                                tempProjects[countryName] = {};
                            }
                            tempProjects[countryName][project[0]] = {
                                'Link': project[1],
                                'Date Created': project[2].substring(0,10),
                                'Organization': project[3],
                                'Deployment Date': project[4].substring(0,10),
                                '# Forms Submitted': project[13],
                                '# Active Mobile Workers': project[6],
                                'Notes': project[17],
                                'Sector': project[23],
                                'Sub-Sector': project[24]
                            };
                        }
                    });
                    projectsByCountryThenName = tempProjects;
    
                    maxNumProjects = Math.max(...Object.keys(projectsByCountryThenName).map(function(countryName) {
                        return Object.keys(projectsByCountryThenName[countryName]).length;
                    }));

                    colorAll();
                }
            });
        };

        that.getNumProjects = function (countryName) {
            countryName = countryName.toLowerCase();
            return Object.keys(projectsByCountryThenName[countryName] || {}).length;
        };

        that.getMaxNumProjects = function () {
            return maxNumProjects;
        };

        // todo: should maybe rename this
        that.getProjectsTable = function (countryName) {
            countryName = countryName.toLowerCase();
            var table = $(document.createElement('table')).addClass("table").addClass("table-hover").addClass("table-condensed");
            var projectsInfo = projectsByCountryThenName[countryName] || {};
            var propertiesToShow = [];
            var propertiesToShow = ['Sector', 'Organization', 'Deployment Date'];

            var row;
            var cell;
            row = $(document.createElement('tr')).addClass('header-row');
            table.append(row);
            cell = $(document.createElement('th'));
            row.append(cell);
            cell.text('Name');
            propertiesToShow.forEach(function(propertyName) {
                cell = $(document.createElement('th'));
                row.append(cell);
                cell.text(propertyName);
            });

            Object.keys(projectsInfo).forEach(function(projectName) {
                row = $(document.createElement('tr'));
                table.append(row);
                cell = $(document.createElement('td'));
                row.append(cell);
                cell.append($(document.createElement('a')).text(projectName).addClass('project-link'));
                propertiesToShow.forEach(function(propertyName) {
                    cell = $(document.createElement('td'));
                    row.append(cell);
                    cell.text(projectsInfo[projectName][propertyName] || "");
                });
            });

            return table;
        };

        // todo: think about reformatting this
        that.getProjectInfoHtml = function (countryName, projectIdentifier) {
            countryName = countryName.toLowerCase();
            var projectInfo = (projectsByCountryThenName[countryName] || {})[projectIdentifier] || {};
            var propertiesToShow = [];
            var propertiesToShow = ['Sector', 'Sub-Sector', 'Organization', 'Deployment Date',
                                    '# Active Mobile Workers', '# Forms Submitted', 'Notes'];

            var html = '';
            propertiesToShow.forEach(function (propertyName) {
                html += '<h5>' + propertyName + ':</h5><span>' + (projectInfo[propertyName] || "") + '</span><br>';
            });

            return html;
        };

        Object.freeze(that);
        return that;
    }();

    var modalController = function(){
        var that = {};

        that.showProjectsTable = function(countryName) {
            $('.country-name').text(countryName);
            $('.modal-body').empty().append(dataController.getProjectsTable(countryName));

            var modalContent = $('.modal-content');
            modalContent.addClass('show-table');
            modalContent.removeClass('show-project-info');
        };

        that.showProjectInfo = function(countryName, projectIdentifier) {
            $('.modal-body').empty().append(dataController.getProjectInfoHtml(countryName, projectIdentifier));
            $('.project-identifier').text(projectIdentifier);

            var modalContent = $('.modal-content');
            modalContent.removeClass('show-table');
            modalContent.addClass('show-project-info');
        };

        Object.freeze(that);
        return that;
    }();

    $(document).on('click', '.project-link', function(evt) {
        // todo: start storing the name of the selected country in a global variable or something, not pulling it out of the DOM when needed
        modalController.showProjectInfo($('.country-name').text(), $(this).text());
    });

    $(document).on('click', '.back', function(evt) {
        modalController.showProjectsTable($('.country-name').text());
    });


    var countriesGeo;
    // A lot of the styling work here is modeled after http://leafletjs.com/examples/choropleth.html
    var map = L.map('map').setView([0, 0], 3)
    var mapId = 'mapbox.dark';
    // todo: move to config somewhere, maybe localSettings.py?
    var accessToken = 'pk.eyJ1IjoiY3p1ZSIsImEiOiJjaWgwa3U5OXIwMGk3a3JrcjF4cjYwdGd2In0.8Tys94ISZlY-h5Y4W160RA';
    L.tileLayer('https://api.tiles.mapbox.com/v4/{id}/{z}/{x}/{y}.png?access_token={accessToken}', {
        maxZoom: 10,
        id: mapId,
        accessToken: accessToken
    }).addTo(map);

    function getColor(featureId) {
        var count = dataController.getNumProjects(featureId);
        if (!count) {
            return COUNTRY_COLORS[0];
        }
        var pct = count / dataController.getMaxNumProjects();
        var index = Math.min(Math.floor(pct * COUNTRY_COLORS.length), COUNTRY_COLORS.length - 1);

        return COUNTRY_COLORS[index];
    }

    function getOpacity(featureId) {
        if (dataController.getNumProjects(featureId)) {
            return .9;
        } else {
            return 0;
        }
    }

    function style(feature) {
        return {
            fillColor: getColor(feature.properties.name),
            weight: 2,
            opacity: 1,
            color: 'white',
            dashArray: '3',
            fillOpacity: getOpacity(feature.properties.name)
        };
    }

    // highlights
    function highlightFeature(e) {
        var layer = e.target;
        layer.setStyle({
            weight: 4,
            color: '#002c5f',
            dashArray: ''
        });
        if (!L.Browser.ie && !L.Browser.opera) {
            layer.bringToFront();
        }
        info.update(layer.feature.properties);
    }

    function resetHighlight(e) {
        countriesGeo.resetStyle(e.target);
        info.update();
    }

    function onEachFeature(feature, layer) {
        layer.on({
            mouseover: highlightFeature,
            mouseout: resetHighlight,
            click: function(e) {
                modalController.showProjectsTable(feature.properties.name);

                // launch the modal
                $('#modal').modal();
            }
        });
    }

    // info control
    var info = L.control();
    info.onAdd = function (map) {
        this._div = L.DomUtil.create('div', 'map-info');
        this.update();
        return this._div;
    };

    // method that we will use to update the control based on feature properties passed in
    info.update = function (props) {
        function _getInfoContent(countryName) {
            var projectCount = dataController.getNumProjects(countryName);
            var message = projectCount ? projectCount + ' projects' : 'no projects';
            return '<b>' + countryName + '</b>: ' + message;
        }
        this._div.innerHTML = (props ? _getInfoContent(props.name) : 'Hover over a country');
    };
    info.addTo(map);

    // add a legend
    var legend = L.control({position: 'bottomleft'});

    legend.onAdd = function (map) {
        var div = L.DomUtil.create('div', 'info legend');

        // get the upper bounds for each bucket
        var countValues = COUNTRY_COLORS.map(function(e, i) {
            // tested this extensively
            var bound = dataController.getMaxNumProjects() * (i+1) / COUNTRY_COLORS.length;
            return Math.max(0, (i < COUNTRY_COLORS.length - 1 && Math.floor(bound) === bound) ? bound - 1 : Math.floor(bound));
        });

        // only include legend items that are actually used right now
        // when there is a low number of max projects (for example, under strict filters), they may not all be included
        var indicesToRemove = [];
        var colors = COUNTRY_COLORS.filter(function(elem, index) {
            if (countValues[index] <= 0 || (index > 0 && countValues[index] == countValues[index-1])) {
                indicesToRemove.push(index);
                return false;
            } else {
                return true;
            }
        });

        countValues = countValues.filter(function(elem, index) {
            return indicesToRemove.indexOf(index) <= -1;
        });

        div.innerHTML += '<i style="background:' + 'black' + '"></i> ' + '0' + '<br>'; 

        // loop through our form count intervals and generate a label with a colored square for each interval
        for (var i = 0; i < countValues.length; i++) {
            div.innerHTML += '<i style="background:' + colors[i] + '"></i> ';
            if (countValues[i-1] !==  undefined) {
                if (countValues[i-1] +1 < countValues[i]) {
                    div.innerHTML += (countValues[i-1] + 1) + '&ndash;'
                }
            } else if (countValues[i] > 1) {
                div.innerHTML += '1&ndash;'
            }
            div.innerHTML += countValues[i] + '<br>';
        }

        return div;
    };

    legend.addTo(map);

    // todo: should probably be getting this from somewhere else and possibly not on every page load.
    $.getJSON('https://raw.githubusercontent.com/dimagi/world.geo.json/master/countries.geo.json', function (data) {
        countriesGeo = L.geoJson(data, {style: style, onEachFeature: onEachFeature}).addTo(map);
        dataController.refreshProjectData({});
    });
});
