# Android GA Tracking Debugger
# Copyright (c) 2025 Alejandro Reinoso
#
# This software is licensed under the Custom Shared-Profit License (CSPL) v1.0.
# See the LICENSE.txt file for details.

import re


def parse_logging_event_line(line):
    """Parses a logging event line for event name, datetime and parameters."""
    datetime_str = line[:18].strip()
    name_match = re.search(r"name=([^,]+)", line)
    params_match = re.search(r"params=Bundle\[\{(.*)\}\]", line)
    if not name_match or not params_match:
        return None
    event_name = name_match.group(1).strip()
    params_str = params_match.group(1).strip()

    params_dict = {}
    raw_pairs = params_str.split(',')
    for pair in raw_pairs:
        pair = pair.strip()
        if '=' in pair:
            k, v = pair.split('=', 1)
            params_dict[k.strip()] = v.strip()

    return {
        "datetime": datetime_str,
        "name": event_name,
        "params": params_dict
    }


def parse_user_property_line(line):
    """Parses a line for user property settings."""
    pat = r"Setting user property:\s+([^,]+),\s+(.*)"
    m = re.search(pat, line)
    if not m:
        pat_fe = r"Setting user property\s*\(FE\):\s+([^,]+),\s+(.*)"
        m = re.search(pat_fe, line)
        if not m:
            return None

    return {
        "name": m.group(1).strip(),
        "value": m.group(2).strip()
    }


def parse_consent_line(line):
    """Parses a line containing consent data into a dictionary format."""
    datetime_str = line[:18].strip()
    found = re.findall(r'(\w+)=(\w+)', line)
    cdict = {
        "datetime": datetime_str,
        "ad_storage": None,
        "analytics_storage": None,
        "ad_user_data": None,
        "ad_personalization": None,
    }
    for (k, v) in found:
        if k in cdict:  # ad_storage, analytics_storage, ad_user_data, ad_personalization
            cdict[k] = v

    if (cdict["ad_storage"] is None
        and cdict["analytics_storage"] is None
            and cdict["ad_user_data"] is None):
        return None
    return cdict
