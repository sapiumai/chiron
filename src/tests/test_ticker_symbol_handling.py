import unittest

import pytest

from chiron.agents.utils.agent_utils import build_instrument_context
from chiron_cli.utils import normalize_ticker_symbol


@pytest.mark.unit
class TickerSymbolHandlingTests(unittest.TestCase):
    def test_normalize_ticker_symbol_preserves_exchange_suffix(self):
        self.assertEqual(normalize_ticker_symbol(" cnc.to "), "CNC.TO")

    def test_build_instrument_context_mentions_exact_symbol(self):
        context = build_instrument_context("7203.T")
        self.assertIn("7203.T", context)
        self.assertIn("exchange suffix", context)

    def test_single_get_ticker_no_shadow(self):
        # Regression: chiron_cli/main.py had a duplicate get_ticker with an empty
        # questionary prompt (rendered as a bare "?") that shadowed the
        # descriptive one in chiron_cli/utils. Keep a single canonical definition.
        import chiron_cli.main
        import chiron_cli.utils
        self.assertIs(chiron_cli.main.get_ticker, chiron_cli.utils.get_ticker)


if __name__ == "__main__":
    unittest.main()
