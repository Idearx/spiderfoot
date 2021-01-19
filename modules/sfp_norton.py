# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_norton
# Purpose:      SpiderFoot plug-in for looking up whether hosts are blocked by
#               Norton DNS (199.85.126.20 and 199.85.127.20)
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     30/05/2018
# Copyright:   (c) Steve Micallef 2018
# Licence:     GPL
# -------------------------------------------------------------------------------

import dns.resolver

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_norton(SpiderFootPlugin):

    meta = {
        'name': "Norton ConnectSafe",
        'summary': "Check if a host would be blocked by Norton ConnectSafe DNS",
        'flags': [""],
        'useCases': ["Investigate", "Passive"],
        'categories': ["Reputation Systems"]
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

    def queryAddr(self, qaddr):
        res = dns.resolver.Resolver()
        res.nameservers = ["199.85.126.20", "199.85.127.20"]

        try:
            addrs = res.resolve(qaddr)
            self.sf.debug("Addresses returned: " + str(addrs))
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
            return None
        self.results[eventData] = True

        # Check that it resolves first, as it becomes a valid
        # malicious host only if NOT resolved by Norton.
        try:
            if self.sf.resolveHost(eventData):
                resolved = True
        except Exception:
            return None

        if resolved:
            found = self.queryAddr(eventData)
            typ = "MALICIOUS_" + eventName
            if eventName == "CO_HOSTED_SITE":
                typ = "MALICIOUS_COHOST"
            if not found:
                evt = SpiderFootEvent(typ, "Blocked by Norton ConnectSafe [" + eventData + "]",
                                      self.__name__, parentEvent)
                self.notifyListeners(evt)

# End of sfp_norton class
