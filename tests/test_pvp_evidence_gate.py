"""Offline regression tests for pvp_evidence_gate."""
import unittest
from dataclasses import replace
from pvp_evidence_gate import Evidence, Phase, inspect_pair

class EvidenceGateTests(unittest.TestCase):
    def setUp(self):
        self.main = Evidence("main", 101, 201, Phase.LOBBY, ("a"*64, "b"*64), "session1", True)
        self.alt = Evidence("alt", 102, 202, Phase.LOBBY, ("c"*64, "d"*64), "session1", True)

    def test_reviewed_still_disables_input(self):
        r = inspect_pair([self.main, self.alt])
        self.assertEqual(r["status"], "observed")
        self.assertFalse(r["input_enabled"])

    def test_unreviewed_pauses(self):
        self.assertEqual(inspect_pair([replace(self.main, reviewed=False), self.alt])["status"], "paused")

    def test_swapped_accounts_pause(self):
        self.assertEqual(inspect_pair([self.alt, self.main])["reason"], "identity_mismatch")

    def test_phase_conflict_pauses(self):
        self.assertEqual(inspect_pair([self.main, replace(self.alt, phase=Phase.BATTLE)])["status"], "paused")

    def test_session_conflict_pauses(self):
        self.assertEqual(inspect_pair([self.main, replace(self.alt, session_id="other")])["status"], "paused")

    def test_repeated_frame_pauses(self):
        self.assertEqual(inspect_pair([replace(self.main, frame_hashes=("a"*64, "a"*64)), self.alt])["status"], "paused")

    def test_malformed_records_pause(self):
        self.assertEqual(inspect_pair([{}, self.alt])["status"], "paused")

if __name__ == "__main__":
    unittest.main()
