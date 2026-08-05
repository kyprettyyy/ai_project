from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "gateway"))

from app.api.routing_audit import verify


class InternalAuditAuthTest(unittest.TestCase):
    @patch("app.api.routing_audit.get_settings")
    def test_valid_internal_token_passes(self, settings) -> None:
        settings.return_value = SimpleNamespace(internal_service_token="internal-test-token")
        verify("internal-test-token")

    @patch("app.api.routing_audit.get_settings")
    def test_invalid_internal_token_is_rejected(self, settings) -> None:
        settings.return_value = SimpleNamespace(internal_service_token="internal-test-token")
        with self.assertRaises(HTTPException) as raised:
            verify("wrong-token")
        self.assertEqual(raised.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
