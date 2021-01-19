# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_opencorporates
# Purpose:      SpiderFoot plug-in for retrieving company information from
#               OpenCorporates.
#
# Author:      <bcoles@gmail.com>
#
# Created:     2018-10-21
# Copyright:   (c) bcoles 2018
# Licence:     GPL
# -------------------------------------------------------------------------------

import urllib
import json

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_opencorporates(SpiderFootPlugin):

    meta = {
        'name': "OpenCorporates",
        'summary': "Look up company information from OpenCorporates.",
        'flags': [""],
        'useCases': ["Passive", "Footprint", "Investigate"],
        'categories': ["Search Engines"],
        'dataSource': {
            'website': "https://opencorporates.com",
            'model': "FREE_NOAUTH_LIMITED",
            'references': [
                "https://api.opencorporates.com/documentation/API-Reference"
            ],
            'favIcon': "https://opencorporates.com/assets/favicons/favicon.png",
            'logo': "https://opencorporates.com/contents/ui/theme/img/oc-logo.svg",
            'description': "The largest open database of companies in the world.\n"
            "As the largest, open database of companies in the world, "
            "our business is making high-quality, official company data openly available. "
            "Data that can be trusted, accessed, analysed and interrogated when and how it’s needed.",
        }
    }

    opts = {
        'confidence': 100,
        'api_key': ''
    }

    optdescs = {
        'confidence': "Confidence that the search result objects are correct (numeric value between 0 and 100).",
        'api_key': 'OpenCorporates.com API key.'
    }

    results = None

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    def watchedEvents(self):
        return ["COMPANY_NAME"]

    def producedEvents(self):
        return ["COMPANY_NAME", "PHYSICAL_ADDRESS", "RAW_RIR_DATA"]

    def searchCompany(self, qry):
        """Search for company name

        Args:
            qry (str): company name

        Returns:
            str
        """

        version = '0.4'

        apiparam = ""
        if not self.opts['api_key'] == "":
            apiparam = "&api_token=" + self.opts['api_key']

        params = urllib.parse.urlencode({
            'q': qry.encode('raw_unicode_escape').decode("ascii", errors='replace'),
            'format': 'json',
            'order': 'score',
            'confidence': self.opts['confidence']
        })

        res = self.sf.fetchUrl(
            f"https://api.opencorporates.com/v{version}/companies/search?{params}{apiparam}",
            timeout=60,  # High timeouts as they can sometimes take a while
            useragent=self.opts['_useragent']
        )

        if res['code'] == "401":
            self.sf.error("Invalid OpenCorporates API key.")
            return None

        if res['code'] == "403":
            self.sf.error("You are being rate-limited by OpenCorporates.")
            return None

        try:
            data = json.loads(res['content'])
        except Exception as e:
            self.sf.debug(f"Error processing JSON response: {e}")
            return None

        if 'results' not in data:
            return None

        return data['results']

    def retrieveCompanyDetails(self, jurisdiction_code, company_number):
        url = f"https://api.opencorporates.com/companies/{jurisdiction_code}/{company_number}"

        if not self.opts['api_key'] == "":
            url += "?api_token=" + self.opts['api_key']

        res = self.sf.fetchUrl(
            url,
            timeout=self.opts['_fetchtimeout'],
            useragent=self.opts['_useragent']
        )

        if res['code'] == "401":
            self.sf.error("Invalid OpenCorporates API key.")
            return None

        if res['code'] == "403":
            self.sf.error("You are being rate-limited by OpenCorporates.")
            return None

        try:
            data = json.loads(res['content'])
        except Exception as e:
            self.sf.debug(f"Error processing JSON response: {e}")
            return None

        if 'results' not in data:
            return None

        return data['results']

    # Extract company address, previous names, and officer names
    def extractCompanyDetails(self, company, sevt):

        # Extract registered address
        location = company.get('registered_address_in_full')

        if location:
            if len(location) < 3 or len(location) > 100:
                self.sf.debug("Skipping likely invalid location.")
            else:
                if company.get('registered_address'):
                    country = company.get('registered_address').get('country')
                    if country:
                        if not location.endswith(country):
                            location += ", " + country

                location = location.replace("\n", ',')
                self.sf.info("Found company address: " + location)
                e = SpiderFootEvent("PHYSICAL_ADDRESS", location, self.__name__, sevt)
                self.notifyListeners(e)

        # Extract previous company names
        previous_names = company.get('previous_names')

        if previous_names:
            for previous_name in previous_names:
                p = previous_name.get('company_name')
                if p:
                    self.sf.info("Found previous company name: " + p)
                    e = SpiderFootEvent("COMPANY_NAME", p, self.__name__, sevt)
                    self.notifyListeners(e)

        # Extract officer names
        officers = company.get('officers')

        if officers:
            for officer in officers:
                n = officer.get('name')
                if n:
                    self.sf.info("Found company officer: " + n)
                    e = SpiderFootEvent("RAW_RIR_DATA", "Possible full name: " + n, self.__name__, sevt)
                    self.notifyListeners(e)

    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if eventData in self.results:
            self.sf.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True

        self.sf.debug(f"Received event, {eventName}, from {srcModuleName}")

        res = self.searchCompany(f"{eventData}*")

        if res is None:
            self.sf.debug("Found no results for " + eventData)
            return

        companies = res.get('companies')

        if not companies:
            self.sf.debug("Found no results for " + eventData)
            return

        for c in companies:
            company = c.get('company')

            if not company:
                continue

            # Check for match
            if not eventData.lower() == company.get('name').lower():
                continue

            # Extract company details from search results
            self.extractCompanyDetails(company, event)

            # Retrieve further details
            jurisdiction_code = company.get('jurisdiction_code')
            company_number = company.get('company_number')

            if not company_number or not jurisdiction_code:
                continue

            res = self.retrieveCompanyDetails(jurisdiction_code, company_number)

            if not res:
                continue

            c = res.get('company')

            if not c:
                continue

            self.extractCompanyDetails(c, event)

# End of sfp_opencorporates class
