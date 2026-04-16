#!/usr/bin/env python3
"""Test ACP transport with Gemini"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "acp"))

from transport import StdioTransport

print("Starting ACP transport for Gemini...")
transport = StdioTransport(worker="gemini", request_timeout=60)

if transport.start():
    print("✅ Transport started")
    
    print("Sending prompt...")
    result = transport.send_prompt("Say hello in one word")
    print(f"Result: {result}")
    
    transport.close()
    print("✅ Transport closed")
else:
    print("❌ Failed to start transport")
    sys.exit(1)
