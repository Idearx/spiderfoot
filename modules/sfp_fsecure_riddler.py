# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_fsecure_riddler
# Purpose:     Query F-Secure Riddler.io API.
#
# Author:      <bcoles@gmail.com>
#
# Created:     2019-09-16
# Copyright:   (c) bcoles 2019
# Licence:     GPL
# -------------------------------------------------------------------------------

import json
import time

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_fsecure_riddler(SpiderFootPlugin):

    meta = {
        'name': "F-Secure Riddler.io",
        'summary': "Obtain network information from F-Secure Riddler.io API.",
        'flags': ["apikey"],
        'useCases': ["Investigate", "Footprint", "Passive"],
        'categories': ["Search Engines"],
        'dataSource': {
            'website': "https://riddler.io/",
            'model': "PRIVATE_ONLY",
            'references': [
                "https://riddler.io/help/api",
                "https://riddler.io/help/search",
                "https://riddler.io/static/riddler_white_paper.pdf",
                "https://www.f-secure.com/en/business/products/vulnerability-management/radar"
            ],
            'apiKeyInstructions': [
                "Registration is disabled for new accounts"
            ],
            'favIcon': "https://riddler.io/static/images/favicon.png",
            'logo': "https://riddler.io/static/images/logo.png",
            'description': "Riddler.io allows you to search in a high quality dataset with more than 396,831,739 hostnames. "
            "Unlike others, we do not rely on simple port scanning techniques - we crawl the web, "
            "ensuring an in-depth quality data set you will not find anywhere else.\n"
            "Use Riddler to enumerate possible attack vectors during your pen-test or use the very same data "
            "to monitor potential threats before it is too late.",
        }
    }

    opts = {
        'verify': True,
        'username': '',
        'password': ''
    }

    optdescs = {
        'verify': 'Verify host names resolve',
        'username': 'F-Secure Riddler.io username',
        'password': 'F-Secure Riddler.io password'
    }

    results = None
    token = None
    errorState = False

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    def watchedEvents(self):
        return ['DOMAIN_NAME', 'INTERNET_NAME',
                'INTERNET_NAME_UNRESOLVED', 'IP_ADDRESS']

    def producedEvents(self):
        return ['INTERNET_NAME', 'AFFILIATE_INTERNET_NAME',
                'INTERNET_NAME_UNRESOLVED', 'AFFILIATE_INTERNET_NAME_UNRESOLVED',
                'DOMAIN_NAME', 'AFFILIATE_DOMAIN_NAME',
                'IP_ADDRESS',
                'PHYSICAL_COORDINATES', 'RAW_RIR_DATA']

    # https://riddler.io/help/api
    def login(self):
        params = {
            'email': self.opts['username'].encode('raw_unicode_escape').decode("ascii"),
            'password': self.opts['password'].encode('raw_unicode_escape').decode("ascii")
        }
        headers = {
            'Content-Type': 'application/json',
        }

        res = self.sf.fetchUrl('https://riddler.io/auth/login',
                               postData=json.dumps(params),
                               headers=headers,
                               useragent=self.opts['_useragent'],
                               timeout=self.opts['_fetchtimeout'])

        if res['content'] is None:
            return None

        try:
            data = json.loads(res['content'])
        except Exception as e:
            self.sf.debug(f"Error processing JSON response from F-Secure Riddler: {e}")
            return None

        try:
            token = data.get('response').get('user').get('authentication_token')
        except Exception:
            self.sf.error('Login failed')
            self.errorState = True
            return None

        if not token:
            self.sf.error('Login failed')
            self.errorState = True
            return None

        self.token = token

        return None

    # https://riddler.io/help/search
    def query(self, qry):
        params = {
            'query': qry.encode('raw_unicode_escape').decode("ascii", errors='replace')
        }
        headers = {
            'Authentication-Token': self.token,
            'Content-Type': 'application/json',
        }

        res = self.sf.fetchUrl('https://riddler.io/api/search',
                               postData=json.dumps(params),
                               headers=headers,
                               useragent=self.opts['_useragent'],
                               timeout=self.opts['_fetchtimeout'])

        time.sleep(1)

        if res['code'] in ["400", "401", "402", "403"]:
            self.sf.error('Unexpected HTTP response code: ' + res['code'])
            self.errorState = True
            return None

        if res['content'] is None:
            return None

        try:
            data = json.loads(res['content'])
        except Exception as e:
            self.sf.debug(f"Error processing JSON response from F-Secure Riddler: {e}")
            return None

        if not data:
            self.sf.debug("No results found for " + qry)
            return None

        return data

    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if self.errorState:
            return None

        self.sf.debug(f"Received event, {eventName}, from {srcModuleName}")

        if srcModuleName == 'sfp_fsecure_riddler':
            self.sf.debug("Ignoring " + eventData + ", from self.")
            return None

        if eventData in self.results:
            self.sf.debug(f"Skipping {eventData}, already checked.")
            return None

        if self.opts['username'] == '' or self.opts['password'] == '':
            self.sf.error('You enabled sfp_fsecure_riddler but did not set an API username/password!')
            self.errorState = True
            return None

        if not self.token:
            self.login()

        self.results[eventData] = True

        data = None

        if eventName in ['INTERNET_NAME', 'DOMAIN_NAME']:
            data = self.query("pld:" + eventData)
        elif eventName == 'IP_ADDRESS':
            data = self.query("ip:" + eventData)

        if not data:
            self.sf.info("No results found for " + eventData)
            return None

        e = SpiderFootEvent('RAW_RIR_DATA', str(data), self.__name__, event)
        self.notifyListeners(e)

        hosts = list()
        addrs = list()
        coords = list()

        for result in data:
            host = result.get('host')

            if not host:
                continue

            if not self.getTarget().matches(host, includeChildren=True, includeParents=True):
                continue

            hosts.append(host)

            addr = result.get('addr')

            if addr:
                addrs.append(addr)

            coord = result.get('cordinates')

            if coord and len(coord) == 2:
                coords.append(str(coord[0]) + ', ' + str(coord[1]))

        if self.opts['verify'] and len(hosts) > 0:
            self.sf.info("Resolving " + str(len(set(hosts))) + " domains ...")

        for host in set(hosts):
            if self.getTarget().matches(host, includeChildren=True, includeParents=True):
                evt_type = 'INTERNET_NAME'
            else:
                evt_type = 'AFFILIATE_INTERNET_NAME'

            if self.opts['verify'] and not self.sf.resolveHost(host):
                self.sf.debug(f"Host {host} could not be resolved")
                evt_type += '_UNRESOLVED'

            evt = SpiderFootEvent(evt_type, host, self.__name__, event)
            self.notifyListeners(evt)

            if self.sf.isDomain(host, self.opts['_internettlds']):
                if evt_type.startswith('AFFILIATE'):
                    evt = SpiderFootEvent('AFFILIATE_DOMAIN_NAME', host, self.__name__, event)
                    self.notifyListeners(evt)
                else:
                    evt = SpiderFootEvent('DOMAIN_NAME', host, self.__name__, event)
                    self.notifyListeners(evt)

        for addr in set(addrs):
            if self.sf.validIP(addr):
                evt = SpiderFootEvent('IP_ADDRESS', addr, self.__name__, event)
                self.notifyListeners(evt)

        for coord in set(coords):
            evt = SpiderFootEvent('PHYSICAL_COORDINATES', coord, self.__name__, event)
            self.notifyListeners(evt)

# End of sfp_fsecure_riddler class
