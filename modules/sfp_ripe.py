# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_ripe
# Purpose:      Queries Internet registryes like RIPE (incl. ARIN) to get
#               netblocks and other bits of info.
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     8/12/2013
# Copyright:   (c) Steve Micallef 2013
# Licence:     GPL
# -------------------------------------------------------------------------------

import json
import re

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_ripe(SpiderFootPlugin):

    meta = {
        'name': "RIPE",
        'summary': "Queries the RIPE registry (includes ARIN data) to identify netblocks and other info.",
        'flags': [""],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Public Registries"],
        'dataSource': {
            'website': "https://www.ripe.net/",
            'model': "FREE_NOAUTH_UNLIMITED",
            'references': [
                "https://www.ripe.net/publications/ipv6-info-centre/training-and-materials",
                "https://www.ripe.net/publications/ipv6-info-centre/ipv6-documents",
                "https://www.ripe.net/manage-ips-and-asns/db/support/documentation/ripe-database-documentation",
                "https://www.ripe.net/manage-ips-and-asns/db/support/documentation/ripe-database-documentation/updating-objects-in-the-ripe-database/6-1-restful-api"
            ],
            'favIcon': "https://www.ripe.net/favicon.ico",
            'logo': "https://www.ripe.net/++resource++ripe.plonetheme.images/RIPE_NCC_logo.png",
            'description': "We're an independent, not-for-profit membership organisation that supports the "
                           "infrastructure of the Internet through technical coordination in our service region. "
                           "Our most prominent activity is to act as the Regional Internet Registry (RIR) providing "
                           "global Internet resources and related services (IPv4, IPv6 and AS Number resources) "
                           "to members in our service region.",
        }
    }

    # Default options
    opts = {}
    optdescs = {}

    results = None
    currentEventSrc = None
    memCache = None
    nbreported = None
    keywords = None
    lastContent = None

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()
        self.memCache = self.tempStorage()
        self.currentEventSrc = None
        self.nbreported = self.tempStorage()
        self.lastContent = None

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    # What events is this module interested in for input
    def watchedEvents(self):
        return ['IP_ADDRESS', 'NETBLOCK_MEMBER', 'NETBLOCK_OWNER',
                'BGP_AS_OWNER', 'BGP_AS_MEMBER']

    # What events this module produces
    # This is to support the end user in selecting modules based on events
    # produced.
    def producedEvents(self):
        return ["NETBLOCK_MEMBER", "NETBLOCK_OWNER", "BGP_AS_MEMBER",
                "RAW_RIR_DATA", "BGP_AS_OWNER"]

    # Fetch content and notify of the raw data
    def fetchRir(self, url):
        if url in self.memCache:
            res = self.memCache[url]
        else:
            res = self.sf.fetchUrl(url, timeout=self.opts['_fetchtimeout'],
                                   useragent=self.opts['_useragent'])
            if res['content'] is not None:
                self.memCache[url] = res
                self.lastContent = res['content']
        return res

    # Get the netblock the IP resides in
    def ipNetblock(self, ipaddr):
        prefix = None

        res = self.fetchRir("https://stat.ripe.net/data/network-info/data.json?resource=" + ipaddr)
        if res['content'] is None:
            self.sf.debug("No Netblock info found/available for " + ipaddr + " at RIPE.")
            return None

        try:
            j = json.loads(res['content'])
        except Exception as e:
            self.sf.debug(f"Error processing JSON response: {e}")
            return None

        prefix = j["data"].get("prefix")
        if prefix is None:
            self.sf.debug("Could not identify network prefix.")
            return None

        return prefix

    # Get the AS owning the netblock
    def netblockAs(self, prefix):
        asn = None

        res = self.fetchRir("https://stat.ripe.net/data/whois/data.json?resource=" + prefix)
        if res['content'] is None:
            self.sf.debug("No AS info found/available for prefix: " + prefix + " at RIPE.")
            return None

        try:
            j = json.loads(res['content'])
            if len(j["data"]["irr_records"]) > 0:
                data = j["data"]["irr_records"][0]
            else:
                data = j["data"]["records"][0]
        except Exception as e:
            self.sf.debug(f"Error processing JSON response: {e}")
            return None

        for rec in data:
            if rec["key"] == "origin":
                asn = rec["value"]
                break

        if asn is None:
            return None

        return str(asn)

    # Owner information about an AS
    def asOwnerInfo(self, asn):
        ownerinfo = dict()
        # Which keys to look for ownership information in (prefix)
        ownerkeys = ["as", "value", "auth", "desc", "org", "mnt", "admin", "tech"]

        res = self.fetchRir("https://stat.ripe.net/data/whois/data.json?resource=" + asn)
        if res['content'] is None:
            self.sf.debug("No info found/available for ASN: " + asn + " at RIPE.")
            return None

        try:
            j = json.loads(res['content'])
            data = j["data"]["records"]
        except Exception as e:
            self.sf.debug(f"Error processing JSON response: {e}")
            return None

        for rec in data:
            for d in rec:
                for k in ownerkeys:
                    if d['key'].lower().startswith(k):
                        if d["value"].lower() not in ["null", "none", "none specified"]:
                            if d["key"] in ownerinfo:
                                ownerinfo[d["key"]].append(d["value"])
                            else:
                                ownerinfo[d["key"]] = [d["value"]]

        self.sf.debug("Returning ownerinfo: " + str(ownerinfo))
        return ownerinfo

    # Netblocks owned by an AS
    def asNetblocks(self, asn):
        netblocks = list()

        res = self.fetchRir("https://stat.ripe.net/data/announced-prefixes/data.json?resource=AS" + asn)
        if res['content'] is None:
            self.sf.debug(f"No netblocks info found/available for AS{asn} at RIPE.")
            return None

        try:
            j = json.loads(res['content'])
            data = j["data"]["prefixes"]
        except Exception as e:
            self.sf.debug(f"Error processing JSON response: {e}")
            return None

        for rec in data:
            netblocks.append(rec["prefix"])
            self.sf.info("Additional netblock found from same AS: " + rec["prefix"])

        return netblocks

    # Neighbours to an AS
    def asNeighbours(self, asn):
        neighbours = list()

        res = self.fetchRir("https://stat.ripe.net/data/asn-neighbours/data.json?resource=AS" + asn)
        if res['content'] is None:
            self.sf.debug(f"No neighbour info found/available for AS{asn} at RIPE.")
            return None

        try:
            j = json.loads(res['content'])
            data = j["data"]["neighbours"]
        except Exception as e:
            self.sf.debug(f"Error processing JSON response: {e}")
            return None

        for rec in data:
            neighbours.append(str(rec['asn']))

        return neighbours

    # Determine whether there is a textual link between the target
    # and the string supplied.
    def findName(self, string):
        # Simplest check to perform..
        for n in self.getTarget().getNames():
            if n in string:
                return True

        if self.keywords is None:
            self.keywords = self.sf.domainKeywords(
                self.getTarget().getNames(),
                self.opts['_internettlds']
            )

        # Slightly more complex..
        rx = [
            r'^{0}[-_/\'\"\\\.,\?\!\s\d]',
            r'[-_/\'\"\\\.,\?\!\s]{0}$',
            r'[-_/\'\"\\\.,\?\!\s]{0}[-_/\'\"\\\.,\?\!\s\d]'
        ]

        # Mess with the keyword as a last resort..
        keywordList = set()
        for kw in self.keywords:
            # Create versions of the keyword, esp. if hyphens are involved.
            keywordList.add(kw)
            keywordList.add(kw.replace('-', ' '))
            keywordList.add(kw.replace('-', '_'))
            keywordList.add(kw.replace('-', ''))

        for kw in keywordList:
            for r in rx:
                if re.match(r.format(kw), string, re.IGNORECASE) is not None:
                    return True

        return False

    # Owns the AS or not?
    def ownsAs(self, asn):
        # Determine whether the AS is owned by our target
        ownerinfo = self.asOwnerInfo(asn)
        owned = False

        if ownerinfo is not None:
            for k in list(ownerinfo.keys()):
                items = ownerinfo[k]
                for item in items:
                    if self.findName(item.lower()):
                        owned = True
        return owned

    # Handle events sent to this module
    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data
        self.currentEventSrc = event

        self.sf.debug(f"Received event, {eventName}, from {srcModuleName}")

        # Don't look up stuff twice
        if eventData in self.results:
            self.sf.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True

        # BGP AS Owner -> Other Netblocks
        if eventName == "BGP_AS_OWNER":
            # Don't report additional netblocks from this AS if we've
            # already found this AS before.
            if eventData not in self.nbreported:
                # Find all the netblocks owned by this AS
                self.nbreported[eventData] = True
                netblocks = self.asNetblocks(eventData)
                if netblocks is not None:
                    for netblock in netblocks:
                        if netblock in self.results:
                            continue

                        # Technically this netblock was identified via the AS, not
                        # the original IP event, so link it to asevt, not event.
                        # Skip IPv6 for now
                        if ":" in netblock:
                            continue
                        evt = SpiderFootEvent("NETBLOCK_OWNER", netblock,
                                              self.__name__, event)
                        self.notifyListeners(evt)
                    evt = SpiderFootEvent("RAW_RIR_DATA", self.lastContent, self.__name__,
                                          event)
                    self.notifyListeners(evt)

            return

        # NETBLOCK -> AS and other owned netblocks
        if eventName.startswith("NETBLOCK_"):
            # Get the BGP AS the netblock is a part of
            asn = self.netblockAs(eventData)
            if asn is None:
                self.sf.debug("Could not identify BGP AS for " + eventData)
                return

            if eventName == "NETBLOCK_OWNER" and self.ownsAs(asn):
                asevt = SpiderFootEvent("BGP_AS_OWNER", asn, self.__name__, event)
                self.notifyListeners(asevt)
                evt = SpiderFootEvent("RAW_RIR_DATA", self.lastContent, self.__name__,
                                      event)
                self.notifyListeners(evt)
            else:
                asevt = SpiderFootEvent("BGP_AS_MEMBER", asn, self.__name__, event)
                self.notifyListeners(asevt)

            return

        # IP ADDRESS -> NETBLOCK
        if eventName == "IP_ADDRESS":
            # Get the Netblock the IP is a part of
            prefix = self.ipNetblock(eventData)
            if prefix is None:
                self.sf.debug("Could not identify network prefix for " + eventData)
                return

            # Get the BGP AS the netblock is a part of
            asn = self.netblockAs(prefix)
            if asn is None:
                self.sf.debug("Could not identify BGP AS for " + prefix)
                return

            if self.sf.validIpNetwork(prefix):
                self.sf.info("Netblock found: " + prefix + "(" + asn + ")")
                evt = SpiderFootEvent("NETBLOCK_MEMBER", prefix, self.__name__, event)
                self.notifyListeners(evt)

# End of sfp_ripe class
