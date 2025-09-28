# Android GA Tracking Debugger
# Copyright (c) 2025 Alejandro Reinoso
#
# This software is licensed under the Custom Shared-Profit License (CSPL) v1.0.
# See the LICENSE.txt file for details.

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
        """
        Deduces ad_personalization status with a single logical exit point,
        following a priority order:
        1. User property 'non_personalized_ads'.
        2. The last known ad_personalization status.
        3. As a last resort, the current value of ad_storage.
        """
        determined_status = None

        # 1. Try to get the direct signal from the user property (_npa).
        npa_key = next(
            (k for k in self.user_properties if "non_personalized_ads" in k), None)

        if npa_key:
            val = self.user_properties[npa_key].strip()
            if val == '0':
                determined_status = "granted"
            elif val == '1':
                determined_status = "denied"

        # 2. If a status has not yet been determined, use fallbacks.
        if determined_status is None:
            if self.current_consent["ad_personalization"] is not None:
                determined_status = self.current_consent["ad_personalization"]
            else:
                # 3. As a last resort, use the ad_storage value.
                determined_status = c["ad_storage"]

        # Single point of modification
        c["ad_personalization"] = determined_status

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

    def has_consent_changed(self, new_filled_consent):
        """
        Checks if the new, filled consent state is different from the current one.
        """
        has_changed = False
        keys_to_check = ["ad_storage", "analytics_storage", "ad_user_data", "ad_personalization"]
        for key in keys_to_check:
            if new_filled_consent.get(key) != self.current_consent.get(key):
                has_changed = True
        return has_changed