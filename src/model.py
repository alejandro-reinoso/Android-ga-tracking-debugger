# src/model.py
'''
model.py manage the status of the app
'''

import queue

class DataModel:
    def __init__(self):
        self.log_queue = queue.Queue()
        self.events_data = []
        self.user_properties = {}
        self.current_consent = {
            "ad_storage": None, "analytics_storage": None,
            "ad_user_data": None, "ad_personalization": None
        }
        self.consent_entries = {}
        self.search_matches = []
        self.current_match_index = -1

    def fill_missing_consent_fields(self, c):
        """Fill in consent fields with 'current_consent' if they don't appear, 
        ad_user_data => if there isn't a previous one => ad_storage."""
        if c["ad_storage"] is None:
            c["ad_storage"] = self.current_consent["ad_storage"]
        if c["analytics_storage"] is None:
            c["analytics_storage"] = self.current_consent["analytics_storage"]
        if c["ad_user_data"] is None:
            if self.current_consent["ad_user_data"] is not None:
                c["ad_user_data"] = self.current_consent["ad_user_data"]
            else:
                c["ad_user_data"] = c["ad_storage"]


    def deduce_ad_personalization(self, c):
        """We use 'non_personalized_ads(_npa)': 1 => denied, 0 => granted. 
        If not available, use the previous value or ad_storage"""
        # TODO: improve this function.
        # print("revisar non_personalized_ads")
        npa_key = None
        for k in self.user_properties:
            if "non_personalized_ads" in k:
                npa_key = k
                break
        if npa_key:
            val = self.user_properties[npa_key].strip()
            if val == '1':
                c["ad_personalization"] = "denied"
            elif val == '0':
                c["ad_personalization"] = "granted"
            else:
                # fallback
                if self.current_consent["ad_personalization"] is not None:
                    c["ad_personalization"] = self.current_consent["ad_personalization"]
                else:
                    c["ad_personalization"] = c["ad_storage"]
        else:
            # no npa key => fallback
            if self.current_consent["ad_personalization"] is not None:
                c["ad_personalization"] = self.current_consent["ad_personalization"]
            else:
                c["ad_personalization"] = c["ad_storage"]


    def add_event(self, event_data):
        """Add a new event to the data list."""
        self.events_data.append(event_data)

    def clear_data(self):
        """Clears all session data."""
        self.events_data.clear()
        self.user_properties.clear()
        self.consent_entries.clear()
        self.search_matches.clear()
        self.current_match_index = -1
        self.current_consent.update({k: None for k in self.current_consent})