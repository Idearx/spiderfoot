# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_email
# Purpose:      SpiderFoot plug-in for scanning retreived content by other
#               modules (such as sfp_spider) and identifying e-mail addresses
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     06/04/2012
# Copyright:   (c) Steve Micallef 2012
# Licence:     GPL
# -------------------------------------------------------------------------------

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_email(SpiderFootPlugin):

    meta = {
        'name': "E-Mail Address Extractor",
        'summary': "Identify e-mail addresses in any obtained data.",
        'useCases': ["Passive", "Investigate", "Footprint"],
        'categories': ["Content Analysis"]
    }

    # Default options
    opts = {
        # options specific to this module
    }

    # Option descriptions
    optdescs = {
    }

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc

        for opt in userOpts.keys():
            self.opts[opt] = userOpts[opt]

    # What events is this module interested in for input
    def watchedEvents(self):
        return ["TARGET_WEB_CONTENT", "BASE64_DATA", "AFFILIATE_DOMAIN_WHOIS",
                "CO_HOSTED_SITE_DOMAIN_WHOIS", "DOMAN_WHOIS", "NETBLOCK_WHOIS",
                "LEAKSITE_CONTENT", "RAW_DNS_RECORDS", "RAW_FILE_META_DATA",
                'RAW_RIR_DATA', "SEARCH_ENGINE_WEB_CONTENT", "SIMILARDOMAIN_WHOIS",
                "SSL_CERTIFICATE_RAW", "SSL_CERTIFICATE_ISSUED", "TCP_PORT_OPEN_BANNER",
                "WEBSERVER_BANNER", "WEBSERVER_HTTPHEADERS"]

    # What events this module produces
    # This is to support the end user in selecting modules based on events
    # produced.
    def producedEvents(self):
        return ["EMAILADDR", "EMAILADDR_GENERIC", "AFFILIATE_EMAILADDR"]

    # Handle events sent to this module
    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        self.sf.debug(f"Received event, {eventName}, from {srcModuleName}")

        emails = self.sf.parseEmails(eventData)
        myres = list()
        for email in emails:
            evttype = "EMAILADDR"
            email = email.lower()

            # Get the domain and strip potential ending .
            mailDom = email.split('@')[1].strip('.')
            if not self.sf.validHost(mailDom, self.opts['_internettlds']):
                self.sf.debug("Skipping " + email + " as not a valid e-mail.")
                return None

            if not self.getTarget().matches(mailDom, includeChildren=True, includeParents=True) and not self.getTarget().matches(email):
                self.sf.debug("External domain, so possible affiliate e-mail")
                evttype = "AFFILIATE_EMAILADDR"

            if eventName.startswith("AFFILIATE_"):
                evttype = "AFFILIATE_EMAILADDR"

            if not evttype.startswith("AFFILIATE_") and email.split("@")[0] in self.opts['_genericusers'].split(","):
                evttype = "EMAILADDR_GENERIC"

            self.sf.info("Found e-mail address: " + email)
            mail = email.strip('.')

            if mail in myres:
                self.sf.debug("Already found from this source.")
                continue

            myres.append(mail)

            evt = SpiderFootEvent(evttype, mail, self.__name__, event)
            if event.moduleDataSource:
                evt.moduleDataSource = event.moduleDataSource
            else:
                evt.moduleDataSource = "Unknown"
            self.notifyListeners(evt)

# End of sfp_email class
