# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_yandexdns
# Purpose:      SpiderFoot plug-in for looking up whether hosts are blocked by
#               Yandex DNS (77.88.8.88 and 77.88.8.2)
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     30/05/2018
# Copyright:   (c) Steve Micallef 2018
# Licence:     GPL
# -------------------------------------------------------------------------------

import dns.resolver

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_yandexdns(SpiderFootPlugin):

    meta = {
        'name': "Yandex DNS",
        'summary': "Check if a host would be blocked by Yandex DNS",
        'flags': [""],
        'useCases': ["Investigate", "Passive"],
        'categories': ["Reputation Systems"],
        'dataSource': {
            'website': "https://yandex.com/",
            'model': "FREE_NOAUTH_UNLIMITED",
            'references': [
                "https://tech.yandex.com/"
            ],
            'favIcon': "https://yastatic.net/iconostasis/_/tToKamh-mh5XlViKpgiJRQgjz1Q.png",
            'logo': "https://yastatic.net/iconostasis/_/tToKamh-mh5XlViKpgiJRQgjz1Q.png",
            'description': "Yandex is a technology company that builds intelligent products and services powered by machine learning. "
            "Our goal is to help consumers and businesses better navigate the online and offline world. "
            "Since 1997, we have delivered world-class, locally relevant search and information services.",
        }
    }

    # Default options
    opts = {
    }

    # Option descriptions
    optdescs = {
    }

    results = None

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    # What events is this module interested in for input
    def watchedEvents(self):
        return ["INTERNET_NAME", "AFFILIATE_INTERNET_NAME", "CO_HOSTED_SITE"]

    # What events this module produces
    # This is to support the end user in selecting modules based on events
    # produced.
    def producedEvents(self):
        return ["MALICIOUS_INTERNET_NAME", "MALICIOUS_AFFILIATE_INTERNET_NAME",
                "MALICIOUS_COHOST"]

    # Query Yandex DNS "safe" servers
    # https://dns.yandex.com/advanced/
    def queryAddr(self, qaddr):
        res = dns.resolver.Resolver()
        res.nameservers = ["77.88.8.88", "77.88.8.2"]

        try:
            addrs = res.resolve(qaddr)
            self.sf.debug(f"Addresses returned: {addrs}")
        except Exception:
            self.sf.debug(f"Unable to resolve {qaddr}")
            return False

        if addrs:
            return True
        return False

    # Handle events sent to this module
    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data
        parentEvent = event
        resolved = False

        self.sf.debug(f"Received event, {eventName}, from {srcModuleName}")

        if eventData in self.results:
            return

        self.results[eventData] = True

        # Check that it resolves first, as it becomes a valid
        # malicious host only if NOT resolved by Yandex.
        try:
            if self.sf.resolveHost(eventData):
                resolved = True
        except Exception:
            self.sf.debug(f"Unable to resolve {eventData}")
            return

        if not resolved:
            return

        found = self.queryAddr(eventData)

        if found:
            return

        if eventName == "CO_HOSTED_SITE":
            typ = "MALICIOUS_COHOST"
        else:
            typ = "MALICIOUS_" + eventName

        evt = SpiderFootEvent(typ, "Blocked by Yandex [" + eventData + "]",
                              self.__name__, parentEvent)
        self.notifyListeners(evt)

# End of sfp_yandexdns class
