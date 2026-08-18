"""Test configuration — sets environment to testing mode before imports.

This MUST be the first conftest loaded by pytest. It sets APP_ENV=testing
so that the Settings validator allows empty secrets during test runs.
"""

from __future__ import annotations

import os

# Set testing mode BEFORE any app imports
os.environ["APP_ENV"] = "testing"
os.environ["JWT_SECRET"] = "test-jwt-secret-not-for-production"
os.environ["GEMINI_API_KEY"] = "test-gemini-key-not-for-production"
