#!/usr/bin/env python
"""Check what curl_cffi returns - content vs text."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from curl_cffi import requests as curl_requests

TEST_URL = "https://missav.live/dass-880-uncensored-leak"

session = curl_requests.Session(impersonate="chrome", timeout=30)
resp = session.get(TEST_URL, impersonate="chrome")

print(f"Type of resp.content: {type(resp.content)}")
print(f"Type of resp.text: {type(resp.text)}")

if isinstance(resp.content, bytes):
    print(f"First 100 bytes (hex): {resp.content[:100].hex()}")
    print(f"First 100 bytes (repr): {repr(resp.content[:100])}")

    # Try decoding as different encodings
    for enc in ['shift_jis', 'utf-8', 'euc-jp', 'cp932', 'latin1']:
        try:
            decoded = resp.content.decode(enc, errors='replace')
            title_match = decoded.find('<title>')
            if title_match != -1:
                snippet = decoded[title_match:title_match+100]
                print(f"\n{enc} decoded (from <title>): {snippet}")
        except Exception as e:
            print(f"\n{enc} failed: {e}")
else:
    print(f"resp.content is a string, not bytes")
    print(f"First 100 chars: {resp.content[:100]}")
