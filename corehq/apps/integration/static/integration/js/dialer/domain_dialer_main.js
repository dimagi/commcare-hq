/**
Based on AWS Boilerplate
**/


hqDefine("integration/js/dialer/domain_dialer_main", [
   "hqwebapp/js/initial_page_data",
   "integration/js/dialer/dialer_utils",
   "detectrtc/DetectRTC",
   "integration/js/dialer/amazon-connect-min",
   "integration/js/dialer/connect-streams-min",
   "commcarehq",
], function (
   initialPageData,
   dialer_utils
) {
    $(function () {
        var inCall = false;
        const customCCPVersion = "CommCare Dialer 1.0";

        function initializeCCP(instanceName) {
        // This function excutes inline with the HTML <body> to initalize the CCP and set up event handlers
        // for agent and contact events.
            
            var signInURL = "https://" + instanceName + ".awsapps.com/connect/login";
            var ccpPath = "https://" + instanceName + ".awsapps.com/connect/ccp-v2#/";
            
            document.getElementById("ConnectLogin").href = signInURL;            
            
            // Initialize the CCP into the container div
            
            connect.core.initCCP(divCCP, {
                ccpUrl:ccpPath,
                loginPopup: true,
                loginPopupAutoClose: true,
                softphone: {allowFramedSoftphone: true}
            });

            // agent events
            connect.agent(function(agent) { 
                
                var agentName = agent.getName();
                document.getElementById("divUserName").innerText = gettext("Welcome, ") + agentName;
                dialer_utils.addToSystemLog(gettext("Agent is logged in: ") + agentName);
                
                if (document.getElementById("checkbox-autodial").checked) {
                    dialEndPoint(document.getElementById('phoneNo').innerText);
                }
            });
            
            // contact events
            connect.contact(function(contact) {

                contact.onConnecting(function(contact) {

                    document.getElementById("contactId").innerHTML = contact.getContactId();
                    document.getElementById("queueName").innerHTML = contact.getQueue().name;
                    document.getElementById("contactStatus").innerHTML = gettext("Connecting...");
                    dialer_utils.addToSystemLog("Connecting to endpoint...");
                    dialer_utils.addToSystemLog("Unique Contact ID assigned: " + contact.getContactId());
                    dialer_utils.addToSystemLog("Call assigned to Queue: " + contact.getQueue().name);
                    inCall = true;
                    document.getElementById("button-dial").disabled = true;
                });

                contact.onConnected(function(contact) {
                    document.getElementById("contactStatus").innerHTML = gettext("Connected");
                    dialer_utils.addToSystemLog("Call connected");
                    inCall = true;
                    document.getElementById("button-dial").disabled = true;
                });
            
                contact.onEnded(function(contact) {
                //    var conStatus = document.getElementById("contactStatus").innerHTML;
                //	if (conStatus != "Disconnected") {
                //		window.alert("Your call has ended. Please close this window now.");    
                //	}
                    document.getElementById("contactStatus").innerHTML = gettext("Disconnected");
                    document.getElementById("button-dial").disabled = false;
                    dialer_utils.addToSystemLog("Call disconnected or cleared");
                    inCall = false
                });
            });
        }

        function initDialer(phone, instanceName) {
        // This function retrieves the phone number parameter (pn) from the URL passed by the
        // calling application.

            dialer_utils.addToSystemLog("Custom CCP Version: " + customCCPVersion);
            
            var phoneNo = "+1" + phone;
            
            document.getElementById("phoneNo").innerText = phoneNo;
            dialer_utils.addToSystemLog("Phone number: (" + phoneNo + ") passed as URL parameter");
            
            // Check user preferences saved in a cookie and apply them to the check boxes

            getPref();
            
            initializeCCP(instanceName);
        }

        function getPref() {
        // This function reads the user preferences cookie 
            
            // Read the check box options
            var chkBox = checkCookie("checkBox");
            
            if (chkBox != "") {
                
                var c = chkBox.split("|");
                var l = c[0];
                var d = c[1];
                
                if (d == "ON") {
                    document.getElementById("checkbox-autodial").checked = true;
                } else {
                    document.getElementById("checkbox-autodial").checked = false;
                }
            }
        }

        function savePreferences() {
        // This functions saves the users check box preferences

            var l = "OFF";
            var d = "OFF";
            
            if (document.getElementById("checkbox-autodial").checked) {
            
                d = "ON";
            }
            
            var chk = l + "|" + d;
            
            // Write cookie - 180 day expiry
            setCookie("checkBox",chk,180);

            dialer_utils.addToSystemLog("Preferences saved");
        }

        function dialEndPoint(targetEndPoint) {
        // This function initiates an outbound dial to phone number endpoint passed
            
            dialer_utils.addToSystemLog("Dialling: " + targetEndPoint);
                
            if (targetEndPoint == "" || targetEndPoint.includes("NOT")) {
                dialer_utils.addToSystemLog("There is no valid phone number available");
                window.alert(gettext("There is no valid phone number available."));
                return(0);
            }
            
            if (document.getElementById("divUserName").innerText.includes("NOT")) {
                dialer_utils.addToSystemLog("You have not logged in");
                window.alert(gettext("You have not logged in."));
                return(0);
            }

            if (inCall) {
                dialer_utils.addToSystemLog("You already have an active call");
                window.alert(gettext("You already have an active call."));
                return(0);
            }
            
            connect.agent(function (agent){
                var endPoint = connect.Endpoint.byPhoneNumber(targetEndPoint);
                agent.connect(endPoint , {
                    success : function(){dialer_utils.addToSystemLog("Call to Connect endpoint API successful")},
                    failure : function(){dialer_utils.addToSystemLog("Call to Connect endpoint API failed")}
                });
            });	
        }


        function checkNetwork() {
        // This function measures network performance on the UDP (media) ports hitting targets east and west
            
            dialer_utils.addToSystemLog("[Check Network] button pressed");

            // Reset all states
            dialer_utils.addToSystemLog("Resetting status lights");
            document.getElementById("imgUDPUSE1").src = dialer_utils.staticAsset("blackLED.png");
            document.getElementById("imgUDPUSW2").src = dialer_utils.staticAsset("blackLED.png");
            
            // UDP (media) ports
            dialer_utils.testUDP();
        }

        function checkMedia() {
        // This function evaluates media device and RTC availability

            dialer_utils.addToSystemLog("[Check Media] button pressed");
            
            function onDetectRTCLoaded() {

                if (DetectRTC.hasSpeakers) {
                    document.getElementById("imgSpeakers").src = dialer_utils.staticAsset("greenLED.png");
                    dialer_utils.addToSystemLog("Speakers are present");
                }
                else {
                    document.getElementById("imgSpeakers").src = dialer_utils.staticAsset("redLED.png");
                    dialer_utils.addToSystemLog("Speakers are not> present");
                }
                
                if (DetectRTC.hasMicrophone) {
                    document.getElementById("imgMicrophone").src = dialer_utils.staticAsset("greenLED.png");
                    dialer_utils.addToSystemLog("Microphone is present");
                }
                else {
                    document.getElementById("imgMicrophone").src = dialer_utils.staticAsset("redLED.png");
                    dialer_utils.addToSystemLog("Microphone is not present");
                }
                
                if (DetectRTC.isWebsiteHasMicrophonePermissions) {
                    document.getElementById("imgMicrophonePermission").src = dialer_utils.staticAsset("greenLED.png");
                    dialer_utils.addToSystemLog("Microphone has access permission");
                }
                else {
                    document.getElementById("imgMicrophonePermission").src = dialer_utils.staticAsset("redLED.png");
                    dialer_utils.addToSystemLog("Microphone does not have access permission");
                }
                
                if (DetectRTC.hasWebcam) {
                    document.getElementById("imgWebCam").src = dialer_utils.staticAsset("greenLED.png");
                    dialer_utils.addToSystemLog("Web Cam is present");
                }
                else {
                    document.getElementById("imgWebCam").src = dialer_utils.staticAsset("redLED.png");
                    dialer_utils.addToSystemLog("Web Cam is not present");
                }
                        
                if (DetectRTC.isWebRTCSupported) {
                    document.getElementById("imgWebRTC").src = dialer_utils.staticAsset("greenLED.png");
                    dialer_utils.addToSystemLog("Browser has RTC support");
                }
                else {
                    document.getElementById("imgWebRTC").src = dialer_utils.staticAsset("redLED.png");
                    dialer_utils.addToSystemLog("Browser does not have RTC support");
                }

            }

            function reloadDetectRTC(callback) {
                DetectRTC.load(function() {
                    onDetectRTCLoaded();

                    if(callback && typeof callback == 'function') {
                        callback();
                    }
                });
            }

            DetectRTC.load(function() {
                reloadDetectRTC();
               // onDetectRTCLoaded();
            });
        }

        function setCookie(cname, cvalue, exdays) {
        // This function writes a cookie
         
            var d = new Date();
            d.setTime(d.getTime() + (exdays*24*60*60*1000));
            var expires = "expires="+ d.toUTCString();
            document.cookie = cname + "=" + cvalue + ";" + expires + ";path=/";
        }

        function checkCookie(attrib) {
        //This function evaluates the value of a single cookie attribute

            var attribVal=getCookie(attrib);
            if (attribVal != "") {
                return(attribVal);
          } else {
                return("");
          }
        }

        function getCookie(cname) {
        //This function reads cookie attribute values

          var name = cname + "=";
          var decodedCookie = decodeURIComponent(document.cookie);
          var ca = decodedCookie.split(';');
          for(var i = 0; i <ca.length; i++) {
            var c = ca[i];
            while (c.charAt(0) == ' ') {
              c = c.substring(1);
            }
            if (c.indexOf(name) == 0) {
              return c.substring(name.length, c.length);
            }
          }
          return "";
        }

        function copyToClipboard() {
        // This function saves the text elements of the log table to the clipboard object

            // The DOM consists of an event container div with two divs within it  - date and content

            var txt = "";
            
            // Get the Parent div
            var p = document.getElementById("divEventWindow");
            
            // Get the children of this div, this will return a collection of divs that contain
            // each message
            var c = p.children;
            
            // Loop each continer div	
            var i;
            var eventTxt = ""
            for (i = 0; i < c.length; i++) {
                
                eventTxt = "";
                
                // Now get the two div elements within this container
                var e = c[i].children;
                
                eventTxt = e[0].innerHTML;   //  This is the date
                eventTxt += "\t";			 //  TAB Char	
                eventTxt += e[1].innerHTML;  //  This is the message body
                eventTxt += "\n";			 //  CRLF	
                txt += eventTxt;
            }

            navigator.clipboard.writeText(txt).then(function() {
                // clipboard successfully set 
                window.alert("Event log has been copied to the system Clipboard");
            }, function(err) {
                // clipboard write failed 
                window.alert("Could not access the system Clipboard: " + err);
            });

        }

        initDialer(initialPageData.get('callout_number'), initialPageData.get('aws_instance_id'));

        document.getElementById('button-dial').addEventListener("click", function() {
            dialEndPoint(document.getElementById('phoneNo').innerText);
        });

        document.getElementById('button-clipboard').addEventListener("click", copyToClipboard);
    
        document.getElementById('checkbox-autodial').addEventListener("change", savePreferences);

        document.getElementById('button-check-media').addEventListener("click", checkMedia);

        document.getElementById('button-check-network').addEventListener("click", checkNetwork);
    });
});
