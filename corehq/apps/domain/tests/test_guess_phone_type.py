from django.test import SimpleTestCase
from corehq.apps.domain.decorators import J2ME, guess_phone_type_from_user_agent, ANDROID


class TestPhoneType(SimpleTestCase):

    def testJavaUserAgents(self):
        corpus = [
            # observed from c2 submission
            'NokiaC2-01/5.0 (11.10) Profile/MIDP-2.1 Configuration/CLDC-1.1 Profile/MIDP-2.0 Configuration/CLDC-1.1',

            # http://developer.nokia.com/community/wiki/User-Agent_headers_for_Nokia_devices
            'Mozilla/5.0 (Series40; Nokia311/03.81; Profile/MIDP-2.1 Configuration/CLDC-1.1) Gecko/20100401 S40OviBrowser/2.2.0.0.31',
            'Mozilla/5.0 (Series40; NokiaX3-02/le6.32; Profile/MIDP-2.1 Configuration/CLDC-1.1) Gecko/20100401 S40OviBrowser/2.0.2.62.10',
            'Mozilla/5.0 (SymbianOS/9.1; U; [en-us]) AppleWebKit/413 (KHTML, like Gecko) Safari/413',
            'Mozilla/5.0 (SymbianOS/9.1; U; [en]; SymbianOS/91 Series60/3.0) AppleWebkit/413 (KHTML, like Gecko) Safari/413',
            'Mozilla/5.0 (SymbianOS/9.1; U; en-us) AppleWebKit/413 (KHTML, like Gecko) Safari/413 es61',
            'Mozilla/5.0 (SymbianOS/9.1; U; [en]; Series60/3.0 NokiaE60/4.06.0) AppleWebKit/413 (KHTML, like Gecko) Safari/413',
            'NokiaN73-2/3.0-630.0.2 Series60/3.0 Profile/MIDP-2.0 Configuration/CLDC-1.1',
            'NokiaN73-2/2.0626 S60/3.0 Profile/MIDP-2.0 Configuration/CLDC-1.1',
            'Mozilla/4.0 (compatible; MSIE 5.0; S60/3.0 NokiaN73-1/2.0(2.0617.0.0.7) Profile/MIDP-2.0 Configuration/CLDC-1.1)',
            'Mozilla/5.0 (SymbianOS/9.2; U; Series60/3.1 NokiaXxx/1.0; Profile/MIDP-2.0 Configuration/CLDC-1.1) AppleWebKit/413 (KHTML, like Gecko) Safari/413',
            'Mozilla/5.0 (SymbianOS/9.3; U; Series60/3.2 NokiaE75-1/110.48.125 Profile/MIDP-2.1 Configuration/CLDC-1.1 ) AppleWebKit/413 (KHTML, like Gecko) Safari/413',
            'Mozilla/5.0 (SymbianOS/9.4; U; Series60/5.0 Nokia5800d-1/21.0.025; Profile/MIDP-2.1 Configuration/CLDC-1.1 ) AppleWebKit/413 (KHTML, like Gecko) Safari/413',
            'Mozilla/5.0 (SymbianOS/9.4; Series60/5.0 NokiaN97-1/12.0.024; Profile/MIDP-2.1 Configuration/CLDC-1.1; en-us) AppleWebKit/525 (KHTML, like Gecko) BrowserNG/7.1.12344',
            'NokiaN90-1/3.0545.5.1 Series60/2.8 Profile/MIDP-2.0 Configuration/CLDC-1.1',
            'Nokia3200/1.0 (5.29) Profile/MIDP-1.0 Configuration/CLDC-1.0 UP.Link/6.3.1.13.0',
            'NokiaN80-3/1.0552.0.7Series60/3.0Profile/MIDP-2.0Configuration/CLDC-1.1',
            'Nokia7610/2.0 (5.0509.0) SymbianOS/7.0s Series60/2.1 Profile/MIDP-2.0 Configuration/CLDC-1.0',
            'Nokia6600/1.0 (5.27.0) SymbianOS/7.0s Series60/2.0 Profile/MIDP-2.0 Configuration/CLDC-1',
            'Nokia6680/1.0 (4.04.07) SymbianOS/8.0 Series60/2.6 Profile/MIDP-2.0 Configuration/CLDC-1.1',
            'Nokia6230/2.0+(04.43)+Profile/MIDP-2.0+Configuration/CLDC-1.1+UP.Link/6.3.0.0.0',
            'Nokia6630/1.0 (2.3.129) SymbianOS/8.0 Series60/2.6 Profile/MIDP-2.0 Configuration/CLDC-1.1',
            'Nokia7600/2.0 (03.01) Profile/MIDP-1.0 Configuration/CLDC-1.0 (Google WAP Proxy/1.0)',
            'NokiaN-Gage/1.0 SymbianOS/6.1 Series60/1.2 Profile/MIDP-1.0 Configuration/CLDC-1.0',
            'Nokia5140/2.0 (3.10) Profile/MIDP-2.0 Configuration/CLDC-1.1',
            'Nokia3510i/1.0 (04.44) Profile/MIDP-1.0 Configuration/CLDC-1.0',
            'Nokia7250i/1.0 (3.22) Profile/MIDP-1.0 Configuration/CLDC-1.0',
            'Nokia7250/1.0 (3.14) Profile/MIDP-1.0 Configuration/CLDC-1.0',
            'Nokia6800/2.0 (4.17) Profile/MIDP-1.0 Configuration/CLDC-1.0 UP.Link/5.1.2.9',
            'Nokia3650/1.0 SymbianOS/6.1 Series60/1.2 Profile/MIDP-1.0 Configuration/CLDC-1.0',
            'Nokia8310/1.0 (05.11) UP.Link/6.5.0.0.06.5.0.0.06.5.0.0.06.5.0.0.0',
            'Mozilla/5.0 (X11; U; Linux armv7l; en-GB; rv:1.9.2b6pre) Gecko/20100318 Firefox/3.5 Maemo Browser 1.7.4.7 RX-51 N900',

            # http://www.zytrax.com/tech/web/mobile_ids.html
            'Mozilla/5.0 (compatible; MSIE 9.0; Windows Phone OS 7.5; Trident/5.0; IEMobile/9.0; NOKIA; Lumia 710)',
            'Nokia2700c-2/2.0 (09.80) Profile/MIDP-2.1 Configuration/CLDC-1.1 UCWEB/2.0(Java; U; MIDP-2.0; en-US; nokia2700c-2) U2/1.0.0 UCBrowser/8.8.1.252 U2/1.0.0 Mobile',
            'Nokia2760/2.0 (06.82) Profile/MIDP-2.1 Configuration/CLDC-1.1',
            'Nokia2700c-2/2.0 (07.80) Profile/MIDP-2.1 Configuration/CLDC-1.1 nokia2700c-2/UC Browser7.7.1.88/69/444 UNTRUSTED/1.0',
            'Opera/9.80 (J2ME/MIDP; Opera Mini/4.1.15082/22.414; U; en) Presto/2.5.25 Version/10.54',
            'Nokia3120Classic/2.0 (06.20) Profile/MIDP-2.1 Configuration/CLDC-1.1',
            'Opera/8.0.1 (J2ME/MIDP; Opera Mini/3.1.9427/1724; en; U; ssr)',
            'Nokia3200/1.0 (5.29) Profile/MIDP-1.0 Configuration/CLDC-1.0 UP.Link/6.3.1.13.0',
            'Nokia3510i/1.0 (04.44) Profile/MIDP-1.0 Configuration/CLDC-1.0',
            'Nokia3650/1.0 SymbianOS/6.1 Series60/1.2 Profile/MIDP-1.0 Configuration/CLDC-1.0',
            'Mozilla/4.0 (compatible; MSIE 4.0; SmartPhone; Symbian OS/1.1.0) Netfront/3.1',
            'Mozilla/5.0 (SymbianOS/9.4; Series60/5.0 Nokia5800d-1/60.0.003; Profile/MIDP-2.1 Configuration/CLDC-1.1 ) AppleWebKit/533.4 (KHTML, like Gecko) NokiaBrowser/7.3.1.33 Mobile Safari/533.4 3gpp-gba',
            'Mozilla/5.0 (SymbianOS/9.4; Series60/5.0 Nokia5230/40.0.003; Profile/MIDP-2.1 Configuration/CLDC-1.1 ) AppleWebKit/525 (KHTML, like Gecko) Version/3.0 BrowserNG/7.2.7.4 3gpp-gba',
            'Mozilla/5.0 (SymbianOS/9.4; Series60/5.0 Nokia5800d-1/50.0.005; Profile/MIDP-2.1 Configuration/CLDC-1.1 ) AppleWebKit/525 (KHTML, like Gecko) Version/3.0 BrowserNG/7.2.3',
            'Nokia5130c-2/2.0 (07.97) Profile/MIDP-2.1 Configuration/CLDC-1.1 nokia5130c-2/UC Browser7.5.1.77/69/351 UNTRUSTED/1.0',
            'Nokia5140/2.0 (3.10) Profile/MIDP-2.0 Configuration/CLDC-1.1',
            'Mozilla/5.0 (SymbianOS/9.4; U; Series60/5.0 Nokia5800d-1b/20.2.014; Profile/MIDP-2.1 Configuration/CLDC-1.1 ) AppleWebKit/413 (KHTML, like Gecko) Safari/413',
            'Nokia6212 classic/2.0 (06.20) Profile/MIDP-2.1 Configuration/CLDC-1.1',
            'Mozilla/5.0 (SymbianOS/9.2; U; Series60/3.1 Nokia6120c/3.83; Profile/MIDP-2.0 Configuration/CLDC-1.1) AppleWebKit/413 (KHTML, like Gecko) Safari/413',
            'Mozilla/4.0 (compatible; MSIE 6.0; Symbian OS; Nokia 6680/5.04.07; 9399) Opera 8.65 [en]',
            'Mozilla/5.0 (SymbianOS/9.1; U; en-us) AppleWebKit/413 (KHTML, like Gecko) Safari/413 es61i',
            'Nokia6230/2.0+(04.43)+Profile/MIDP-2.0+Configuration/CLDC-1.1+UP.Link/6.3.0.0.0',
            'Nokia6630/1.0 (2.3.129) SymbianOS/8.0 Series60/2.6 Profile/MIDP-2.0 Configuration/CLDC-1.1',
            'Mozilla/4.1 (compatible; MSIE 5.0; Symbian OS; Nokia 6600;432) Opera 6.10 [en]',
            'Nokia6600/1.0 (5.27.0) SymbianOS/7.0s Series60/2.0 Profile/MIDP-2.0 Configuration/CLDC-1',
            'Nokia6680/1.0 (4.04.07) SymbianOS/8.0 Series60/2.6 Profile/MIDP-2.0 Configuration/CLDC-1.1',
            'Mozilla/4.1 (compatible; MSIE 5.0; Symbian OS; Nokia 6600;452) Opera 6.20  [en-US]',
            'Nokia6800/2.0 (4.17) Profile/MIDP-1.0 Configuration/CLDC-1.0 UP.Link/5.1.2.9',
            'Nokia7610/2.0 (7.0642.0) SymbianOS/7.0s Series60/2.1 Profile/MIDP-2.0 Configuration/CLDC-1.0/UC Browser7.9.1.120/27/351/UCWEB',
            'Nokia7250I/1.0 (3.22) Profile/MIDP-1.0 Configuration/CLDC-1.0',
            'Nokia7250/1.0 (3.14) Profile/MIDP-1.0 Configuration/CLDC-1.0',
            'Nokia7610/2.0 (5.0509.0) SymbianOS/7.0s Series60/2.1 Profile/MIDP-2.0 Configuration/CLDC-1.0',
            'Nokia8310/1.0 (05.11) UP.Link/6.5.0.0.06.5.0.0.06.5.0.0.06.5.0.0.0',
            'Mozilla/4.0 (compatible; MSIE 5.0; Series80/2.0 Nokia9300/05.22 Profile/MIDP-2.0 Configuration/CLDC-1.1)',
            'Mozilla/4.0 (compatible; MSIE 5.0; Series80/2.0 Nokia9500/4.51 Profile/MIDP-2.0 Configuration/CLDC-1.1)',
            'NokiaC3-00/5.0 (04.60) Profile/MIDP-2.1 Configuration/CLDC-1.1 Mozilla/5.0 AppleWebKit/420+ (KHTML, like Gecko) Safari/420+',
            'Mozilla/5.0 (SymbianOS/9.3; Series60/3.2 NokiaE55-1/034.001; Profile/MIDP-2.1 Configuration/CLDC-1.1) AppleWebKit/525 (KHTML, like Gecko) Version/3.0 BrowserNG/7.1.5',
            'Opera/9.80 (S60; SymbOS; Opera Mobi/499; U; en-GB) Presto/2.4.18 Version/10.00',
            'Mozilla/5.0 (SymbianOS/9.1; U; en-us) AppleWebKit/413 (KHTML, like Gecko) Safari/413 es61i',
            'Opera/9.60 (J2ME/MIDP; Opera Mini/4.2.13918/488; U; en) Presto/2.2.0',
            'Mozilla/5.0 (SymbianOS/9.2; U; Series60/3.1 NokiaE63-3/100.21.110; Profile/MIDP-2.0 Configuration/CLDC-1.1 ) AppleWebKit/413 (KHTML, like Gecko) Safari/413',
            'Mozilla/5.0 (SymbianOS/9.1; U; en-us) AppleWebKit/413 (KHTML, like Gecko) Safari/413',
            'Mozilla/5.0 (SymbianOS/9.2; U; Series60/3.1 NokiaE90-1/07.24.0.3; Profile/MIDP-2.0 Configuration/CLDC-1.1 ) AppleWebKit/413 (KHTML, like Gecko) Safari/413 UP.Link/6.2.3.18.0',
            'Mozilla/5.0 (MeeGo; NokiaN9) AppleWebKit/534.13 (KHTML, like Gecko) NokiaBrowser/8.5.0 Mobile Safari/534.13',
            'NokiaN70-1/5.0737.3.0.1 Series60/2.8 Profile/MIDP-2.0 Configuration/CLDC-1.1/UC Browser7.8.0.95/27/352',
            'Mozilla/5.0 (SymbianOS/9.3; U; Series60/3.2 NokiaN79-1/32.001; Profile/MIDP-2.1 Configuration/CLDC-1.1) AppleWebKit/413 (KHTML, like Gecko) Safari/413',
            'Mozilla/5.0 (SymbianOS/9.4; Series60/5.0 NokiaN97-1/20.0.019; Profile/MIDP-2.1 Configuration/CLDC-1.1) AppleWebKit/525 (KHTML, like Gecko) BrowserNG/7.1.18124',
            'Mozilla/5.0 (SymbianOS/9.3; U; Series60/3.2 NokiaN85-1/31.002; Profile/MIDP-2.1 Configuration/CLDC-1.1) AppleWebKit/413 (KHTML, like Gecko) Safari/413',
            # 'Mozilla/5.0 (X11; U; Linux armv61; en-US; rv:1.9.1b2pre) Gecko/20081015 Fennec/1.0a1',   # Alpha version of Mozilla Fennec (mobile Firefox) on Nokia N800.
            'Mozilla/5.0 (X11; U; Linux armv7l; en-GB; rv:1.9.2a1pre) Gecko/20090928 Firefox/3.5 Maemo Browser 1.4.1.22 RX-51 N900',
            # 'Mozilla/5.0 (X11; U; Linux armv6l; en-us) AppleWebKit/528.5+ (KHTML, like Gecko, Safari/528.5+) tear',  # Tear 0.3 (Beta) on Nokia N800 under Mer
            # 'Mozilla/5.0 (X11; U; Linux armv6l; en-us) AppleWebKit/528.5+ (KHTML, like Gecko, Safari/528.5+) midori',  # Midori on Nokia n800 tablet device.
            # 'Links (2.1pre31; Linux 2.6.21-omap1 armv6l; x)',  # Links 2.1 preview 31 on a Nokia N800 tablet under OS2008
            # 'Mozilla/5.0 (X11; U; Linux armv6l; en-US; rv: 1.9.1a2pre) Gecko/20080813221937 Prism/0.9.1',  # Prism on a Nokia N800 tablet under OS2008
            # 'Mozilla/5.0 (X11; U; Linux armv6l; en-US; rv:1.9a6pre) Gecko/20070810 Firefox/3.0a1 Tablet browser 0.1.16 RX-34_2007SE_4.2007.38-2',  # Nokia N800 (Internet tablet) (v.20.0.015) running MicroB (a version of FF3) with embedded Flash 9 player
            # 'Opera/9.50 (J2ME/MIDP; Opera Mini/4.1.10781/298; U; en)',  # Nokia N95 (v.20.0.015) running Opera 9.50 MINI
            'Mozilla/5.0 (SymbianOS/9.2; U; Series60/3.1 NokiaE71-1/100.07.76; Profile/MIDP-2.0 Configuration/CLDC-1.1 ) AppleWebKit/413 (KHTML, like Gecko) Safari/413',
            'Opera/8.01 (J2ME/MIDP; Opera Mini/3.0.6306/1528; en; U; ssr)',
            'Mozilla/4.0 (compatible; MSIE 6.0; ; Linux armv5tejl; U) Opera 8.02 [en_US] Maemo browser 0.4.31 N770/SU-18',
            'NokiaN80-3/1.0552.0.7Series60/3.0Profile/MIDP-2.0Configuration/CLDC-1.1',
            'Mozilla/5.0 (SymbianOS/9.1; U; en-us) AppleWebKit/413 (KHTML, like Gecko) Safari/413',
            # 'Mozilla/5.0 (X11; U; Linux armv6l; en-US; rv:1.9a6pre) Gecko/20070807 Firefox/3.0a1 Tablet browser 0.1.16 RX-34_2007SE_4.2007.26-8',  # Firefox on Nokia N800 Tablet PC
            'NokiaN90-1/3.0545.5.1 Series60/2.8 Profile/MIDP-2.0 Configuration/CLDC-1.1',
            'NokiaN-Gage/1.0 SymbianOS/6.1 Series60/1.2 Profile/MIDP-1.0 Configuration/CLDC-1.0',
        ]
        for java_agent in corpus:
            self.assertEqual(J2ME, guess_phone_type_from_user_agent(java_agent), 'j2me user agent detection failed for {}'.format(java_agent))

    def testAnroidUserAgents(self):
        corpus = [
            # http://www.zytrax.com/tech/web/mobile_ids.html
            # android like things
            'Mozilla/5.0 (Linux; Android 4.1.1; Transformer Prime TF201 Build/JRO03C) AppleWebKit/535.19 (KHTML, like Gecko) Chrome/18.0.1025.166  Safari/535.19',
            'Mozilla/5.0 (Linux; U; Android 4.0.4; en-us; Transformer TF101 Build/IMM76I) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Safari/534.30',
            'Mozilla/5.0 (Linux; U; Android 2.3.6; en-us; VS840 4G Build/GRK39F) AppleWebKit/533.1 (KHTML, like Gecko) Version/4.0 Mobile Safari/533.1',
            'Mozilla/5.0 (Linux; U; Android 2.2.1; en-us; MB525 Build/3.4.2-107_JDN-9) AppleWebKit/533.1 (KHTML, like Gecko) Version/4.0 Mobile Safari/533.1',
            'Mozilla/5.0 (Linux; U; Android 2.1-update1-1.0.19; en-us; NXM736 Build/ECLAIR) AppleWebKit/530.17 (KHTML, like Gecko) Version/4.0 Mobile Safari/530.17',
            'Mozilla/5.0 (Linux; U; Android 2.2; de-de; U0101HA Build/FRF85B) AppleWebKit/533.1 (KHTML, like Gecko) Version/4.0 Mobile Safari/533.1',
            'Mozilla/5.0 (Linux; U; Android 2.2.1; de-de; SP-60 Build/MASTER) AppleWebKit/533.1 (KHTML, like Gecko) Version/4.0 Mobile Safari/533.1',
            'Mozilla/5.0 (Linux; U; Android 2.2; en-gb; ViewPad7 Build/FRF91) AppleWebKit/533.1 (KHTML, like Gecko) Version/4.0 Mobile Safari/533.1',
            'Mozilla/5.0 (Linux; U; Android 2.1-2010.11.4; de-de; XST2 Build/ECLAIR) AppleWebKit/530.17 (KHTML, like Gecko) Version/4.0 Mobile Safari/530.17',
            'Mozilla/5.0 (Linux; U; Android 1.0.3; de-de; A80KSC Build/ECLAIR) AppleWebKit/530.17 (KHTML, like Gecko) Version/4.0 Mobile Safari/530.17',
            'Mozilla/5.0 (Linux; U; Android 2.2.1; en-au; eeepc Build/MASTER) AppleWebKit/533.1 (KHTML, like Gecko) Version/4.0 Mobile Safari/533.1',
            'Mozilla/5.0 (Linux; U; Android 1.6; en-us; xpndr_ihome Build/DRD35) AppleWebKit/528.5+ (KHTML, like Gecko) Version/3.1.2 Mobile Safari/525.20.1',
            'Mozilla/5.0 (Linux; U; Android 2.2.1; fr-ch; A43 Build/FROYO) AppleWebKit/533.1 (KHTML, like Gecko) Version/4.0 Mobile Safari/533.1',
            'Mozilla/5.0 (Linux; U; Android 2.2.1; de-de; X2 Build/FRG83) AppleWebKit/533.1 (KHTML, like Gecko) Version/4.0 Mobile Safari/533.1',
        ]
        for android_agent in corpus:
            self.assertEqual(ANDROID, guess_phone_type_from_user_agent(android_agent), 'android user agent detection failed for {}'.format(android_agent))

    def testDefaultIsAndroid(self):
        for empty in [None, '']:
            self.assertEqual(ANDROID, guess_phone_type_from_user_agent(empty))
