/**
Based on AWS boilerplate
**/

hqDefine('widget/js/dialer_utils',[], function () {

    function getFormattedDate() {
    // This function returns a formatted date for use in the log table

        var d = new Date();

        var month=new Array();
        month[0]="Jan";
        month[1]="Feb";
        month[2]="Mar";
        month[3]="Apr";
        month[4]="May";
        month[5]="Jun";
        month[6]="Jul";
        month[7]="Aug";
        month[8]="Sep";
        month[9]="Oct";
        month[10]="Nov";
        month[11]="Dec";

        var hours = d.getHours();
        var minutes = d.getMinutes();
        var seconds = d.getSeconds();
      
        if (minutes < 10) {
            minutes = "0" + minutes;
        }

        if (seconds < 10) {
            seconds = "0" + seconds;
        }
      
        var strTime = hours + ":" + minutes + ":" + seconds;
        var strDate = strTime + " " + d.getDate() + "-" + month[d.getMonth()];
        return(strDate);
    }

    function addToSystemLog(logTxt) {
    // This function adds an entry to the on screen diagnostic log table

        // Create the new event container
        var newContainer = document.createElement("DIV");

        // Assign the correct class
        newContainer.className = "eventContainer";

        // Attach it to the parent
        document.getElementById("divEventWindow").appendChild(newContainer);


        // Create the new date div
        var newDate = document.createElement("DIV");

        // Assign the correct class
        newDate.className = "eventDate";

        // Assign a value

        var d = getFormattedDate();
        newDate.innerHTML = d;

        // Attach it to the parent
        newContainer.appendChild(newDate);


        // Create the new text div
        var newText = document.createElement("DIV");

        // Assign the correct class
        newText.className = "eventText";

        // Assign a value
        newText.innerHTML = logTxt;

        // Attach it to the parent
        newContainer.appendChild(newText);

    }

    var request_no = 1;
    var success = new Object();

    var all_regions = {
      'US-East-1': {
        'mediaBlocks': [
          {
            'startIp': '52.55.191.224',
            'ipsInBlock': '8'
          },
          {
            'startIp': '18.233.213.128',
            'ipsInBlock': '8'
          }
        ]
      },
        'US-West-2': {
        'mediaBlocks': [
          {
            'startIp':'54.190.198.32',
            'ipsInBlock': '8'
          },
          {
            'startIp':'18.236.61.0',
            'ipsInBlock': '8'
          }
        ]
      }
    }

    function checkTURNServer(region, turnConfig, timeout) {
      
        request_no++;
      
        return new Promise(function (resolve, reject) {

            setTimeout(function () {
            if (promiseResolved) return;
            resolve(false);
            promiseResolved = true;
            }, timeout || 5000);

            var promiseResolved = false
            , myPeerConnection = window.RTCPeerConnection || window.mozRTCPeerConnection || window.webkitRTCPeerConnection   //compatibility for firefox and chrome
            , pc = new myPeerConnection({ iceServers: [turnConfig] })
            , noop = function () { };
            pc.createDataChannel("");    //create a bogus data channel
            pc.createOffer(function (sdp) {
                if (sdp.sdp.indexOf('typ relay') > -1) { // sometimes sdp contains the ice candidates...
                promiseResolved = true;
                resolve(true);
            }
            pc.setLocalDescription(sdp, noop, noop);
            }, noop);    // create offer and set local description
            pc.onicecandidate = function (ice) {  //listen for candidate events
                var ipRe = /\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b/;

                try {
                    testIp = ice.candidate.candidate.match(ipRe);
                    if (isRfc1918(testIp)) {
                        if (! success.hasOwnProperty(region) ) {
                            updateSuccessImage(region);
                            success[region] = "PASSED";
                            addToSystemLog("PASS for region: " + region);
                        }
                    }
                    if (promiseResolved || !ice || !ice.candidate || !ice.candidate.candidate || !(ice.candidate.candidate.indexOf('typ relay') > -1)) return;
              
                    promiseResolved = true;
                    resolve(true);
                }
                catch {}
            };
        });	
    }

    function isRfc1918(ipIn){
        
      
        var ipToTest = new String(ipIn);
        var rfc1918_1_re = /^10\..*$/;
        var rfc1918_2_re = /^172\.(16|17|18|19|20|21|22|23|24|25|26|27|28|29|30|31).*$/;
        var rfc1918_3_re = /^192\.168\..*$/;

        if ( ipToTest.match(rfc1918_1_re) ){
            return false;
        } else if ( ipToTest.match(rfc1918_2_re) ) {
            return false;
        } else if ( ipToTest.match(rfc1918_3_re) ) {
            return false;
        } else {
            return true;
        }
    }


    function updateSuccessImage(region) {

        var docTarget = "";

        switch(region) {
          case "US-East-1":
                docTarget = "imgUDPUSE1";
            break;
          case "US-West-2":
                docTarget = "imgUDPUSW2";
            break;
          default:
            // code block
        }
        
        // Update image to green unless it was set previously set to another
        
        if (document.getElementById(docTarget).src.includes("black"))
        {
            document.getElementById(docTarget).src="/static/widget/images/greenLED.png";
        }

    }


    function test_turn(region, turn_url, user, cred) {
        
        checkTURNServer(region, {
        url: turn_url,
        username: user,
        credential: cred
      }, 1000).then(function (bool) {
        var active = bool ? 'yes' : 'no';
      }).catch(console.error.bind(console));
    }



    function iterate_through_array(region, startIp, ipsInBlock){
      
        addToSystemLog("Checking region " + region + " and startIP: " + startIp);
        
        var octets = startIp.split(".");
        var first = octets[0];
        var second = octets[1];
        var third = octets[2];
        var fourth = octets[3];
        var endOctet = Number(fourth) + Number(ipsInBlock);

        for ( var lastOctet = Number(fourth); (lastOctet <= Number(fourth) + Number(ipsInBlock)) && (lastOctet <= 255); lastOctet++){
            var ipToTest = first + "." + second + "." + third + "." + lastOctet;
            test_turn(region, "stun:" + ipToTest + ":3478","test","test");
        }
    }


    function udpFailure() {
      
        for (var region in all_regions) {
            
            if (!success.hasOwnProperty(region) ){
                
                var docTarget = "";
                switch(region) {
                case "US-East-1":
                    docTarget = "imgUDPUSE1";
                    break;
                case "US-West-2":
                    docTarget = "imgUDPUSW2";
                    break;
                default:
                // code block
                }
            
                addToSystemLog("UDP 3478 failure for region : " + region);
                document.getElementById(docTarget).src="/static/widget/images/redLED.png";
            }
        }
    }

    function testUDP() {
      
        var thisStartIp;
        var thisIpsInBlock;
        
        for (var member in success) delete success[member];
        

        for (var region in all_regions) {

            for (var key in all_regions[region]) {
                
                for (var arrayindex = 0; arrayindex < all_regions[region][key].length; arrayindex++) {

                    thisStartIp = all_regions[region][key][arrayindex].startIp;
                    thisIpsInBlock = all_regions[region][key][arrayindex].ipsInBlock;

                    iterate_through_array(region, thisStartIp, thisIpsInBlock);
            
                }
            }
        }

      setTimeout(udpFailure,5000);
    }

    return {
        testUDP : testUDP,
        addToSystemLog : addToSystemLog
    };
});
