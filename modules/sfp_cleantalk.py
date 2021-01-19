# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_cleantalk
# Purpose:     Checks if a netblock or IP address is on CleanTalk.org's spam IP list.
#
# Author:      steve@binarypool.com
#
# Created:     05/08/2018
# Copyright:   (c) Steve Micallef, 2018
# Licence:     GPL
# -------------------------------------------------------------------------------

from netaddr import IPAddress, IPNetwork

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_cleantalk(SpiderFootPlugin):

    meta = {
        'name': "CleanTalk Spam List",
        'summary': "Check if a netblock or IP address is on CleanTalk.org's spam IP list.",
        'flags': [""],
        'useCases': ["Investigate", "Passive"],
        'categories': ["Reputation Systems"],
        'dataSource': {
            'website': "https://cleantalk.org",
            'model': "FREE_NOAUTH_UNLIMITED",
            'references': [
                "https://cleantalk.org/help",
                "https://cleantalk.org/help/introduction",
                "https://cleantalk.org/help/api-spam-check",
                "https://cleantalk.org/wordpress-security-malware-firewall",
                "https://cleantalk.org/price-anti-spam",
                "https://cleantalk.org/ssl-certificates/cheap-positivessl-certificate",
                "https://cleantalk.org/email-checker",
                "https://cleantalk.org/blacklists"
            ],
            'favIcon': "https://cleantalk.org/favicons/favicon-16x16.png",
            'logo': "https://cleantalk.org/favicons/favicon-16x16.png",
            'description': "CleanTalk is a Cloud-Based spam filtering service that allows you to protect your website from spam. "
            "CleanTalk provides spam protection that invisible to visitors "
            "without using captcha or other methods when visitors have to prove that they are real people.\n"
            "CleanTalk provides cloud anti-spam solutions for CMS and we developed plugins for the most of popular "
            "CMS: WordPress anti-spam plugin, Joomla anti-spam plugin, Drupal and etc. "
            "With our simple cloud spam checker, you can be sure your website is protected from spam bots, spam comments, and users.",
        }
    }

    # Default options
    opts = {
        'checkaffiliates': True,
        'cacheperiod': 18,
        'checknetblocks': True,
        'checksubnets': True
    }

    # Option descriptions
    optdescs = {
        'checkaffiliates': "Apply checks to affiliate IP addresses?",
        'cacheperiod': "Hours to cache list data before re-fetching.",
        'checknetblocks': "Report if any malicious IPs are found within owned netblocks?",
        'checksubnets': "Check if any malicious IPs are found within the same subnet of the target?"
    }

    results = None
    errorState = False

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()
        self.errorState = False

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    # What events is this module interested in for input
    def watchedEvents(self):
        return ["IP_ADDRESS", "AFFILIATE_IPADDR",
                "NETBLOCK_MEMBER", "NETBLOCK_OWNER"]

    # What events this module produces
    def producedEvents(self):
        return ["MALICIOUS_IPADDR", "MALICIOUS_AFFILIATE_IPADDR",
                "MALICIOUS_SUBNET", "MALICIOUS_NETBLOCK"]

    def query(self, qry, targetType):
        cid = "_cleantalk"
        url = "https://iplists.firehol.org/files/cleantalk_7d.ipset"

        data = dict()
        data["content"] = self.sf.cacheGet("sfmal_" + cid, self.opts.get('cacheperiod', 0))

        if data["content"] is None:
            data = self.sf.fetchUrl(url, timeout=self.opts['_fetchtimeout'], useragent=self.opts['_useragent'])

            if data["code"] != "200":
                self.sf.error("Unable to fetch %s" % url)
                self.errorState = True
                return None

            if data["content"] is None:
                self.sf.error("Unable to fetch %s" % url)
                self.errorState = True
                return None

            self.sf.cachePut("sfmal_" + cid, data['content'])

        for line in data["content"].split('\n'):
            ip = line.strip().lower()

            if ip.startswith('#'):
                continue

            if targetType == "netblock":
                try:
                    if IPAddress(ip) in IPNetwork(qry):
                        self.sf.debug("%s found within netblock/subnet %s in CleanTalk Spam List." % (ip, qry))
                        return url
                except Exception as e:
                    self.sf.debug("Error encountered parsing: %s" % e)
                    continue

            if targetType == "ip":
                if qry.lower() == ip:
                    self.sf.debug("%s found in CleanTalk Spam List." % qry)
                    return url

        return None

    # Handle events sent to this module
    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        self.sf.debug(f"Received event, {eventName}, from {srcModuleName}")

        if eventData in self.results:
            self.sf.debug(f"Skipping {eventData}, already checked.")
            return None

        if self.errorState:
            return None

        self.results[eventData] = True

        if eventName == 'IP_ADDRESS':
            targetType = 'ip'
            evtType = 'MALICIOUS_IPADDR'
        elif eventName == 'AFFILIATE_IPADDR':
            if not self.opts.get('checkaffiliates', False):
                return None
            targetType = 'ip'
            evtType = 'MALICIOUS_AFFILIATE_IPADDR'
        elif eventName == 'NETBLOCK_OWNER':
            if not self.opts.get('checknetblocks', False):
                return None
            targetType = 'netblock'
            evtType = 'MALICIOUS_NETBLOCK'
        elif eventName == 'NETBLOCK_MEMBER':
            if not self.opts.get('checksubnets', False):
                return None
            targetType = 'netblock'
            evtType = 'MALICIOUS_SUBNET'
        else:
            return None

        self.sf.debug("Checking maliciousness of %s with CleanTalk Spam List" % eventData)

        url = self.query(eventData, targetType)

        if not url:
            return None

        text = "CleanTalk Spam List [%s]\n<SFURL>%s</SFURL>" % (eventData, url)
        evt = SpiderFootEvent(evtType, text, self.__name__, event)
        self.notifyListeners(evt)

# End of sfp_cleantalk class
