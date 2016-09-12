/*
 * Common workflow methods/widgets go here.
 */ 

function qSelectReqd (caption, choices, help, ans) {
  return new wfQuestion({caption: caption, type: 'select', choices: uniqifyChoices(choices), required: true, helptext: help, answer: ans});
}

function uniqifyChoices (choices) {
  var getcapt = function (choice) {
    return (choice instanceof Object ? choice.lab : choice);
  }

  var setcapt = function (choices, i, capt) {
    if (choices[i] instanceof Object) {
      choices[i].lab = capt;
    } else {
      choices[i] = capt;
    }
  }

  var duplicateChoices = true;
  while (duplicateChoices) {
    captions = []
    indices = []
    for (var i = 0; i < choices.length; i++) {
      var capt = getcapt(choices[i]);
      var k = captions.indexOf(capt);
      if (k == -1) {
        k = captions.length;
        captions.push(capt);
        indices[k] = []
      }
      indices[k].push(i);
    }

    duplicateChoices = false;
    for (var i = 0; i < indices.length; i++) {
      if (indices[i].length > 1) {
        duplicateChoices = true;
        for (var j = 0; j < indices[i].length; j++) {
          setcapt(choices, indices[i][j], getcapt(choices[indices[i][j]]) + ' (' + (j + 1) + ')');
        }
      }
    }
  }

  return choices;
}

function get_usernames() {
    res = jQuery.ajax({url: '/api/usernames/', 
                              type: 'GET', 
                              async: false,
                              success: function(data, textStatus, request) {
                                    json_res = JSON.parse(data);
                                    request.result = json_res;
                                },
                       });
    return res.result;
}
        
function qUsernameList(title) {
    var usernames = get_usernames();
    title = title || "Please select your username";
    return qSelectReqd(title, zip_choices(usernames, usernames));
}

function get_roles() {
    res = jQuery.ajax({url: '/api/roles/', 
                              type: 'GET', 
                              async: false,
                              success: function(data, textStatus, request) {
                                    json_res = JSON.parse(data);
                                    request.result = json_res;
                                },
                       });
    return res.result;
}
        

function qRoleList(title) {
    var roles = get_roles();
    title = title || "Please choose the user's role";
    return qSelectReqd(title, zip_choices(roles, roles));
}

function chwZoneChoices (num_zones) {
  var choices = [];
  for (var i = 1; i <= num_zones; i++) {
    choices.push({lab: "Zone " + i, val: 'zone' + i});
  }
  choices.push({lab: "Lives outside catchment area", val: 'outside_catchment_area'});
  choices.push({lab: "Don't know which zone", val: 'unknown'});

  return choices;
}

function zip_choices (labels, values) {
  var choices = [];
  for (var i = 0; i < labels.length; i++) {
    choices.push({lab: labels[i], val: values[i]});
  }
  return choices;
}