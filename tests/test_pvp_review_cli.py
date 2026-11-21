import unittest
from pvp_review_cli import review_payload

H1 = "a" * 64
H2 = "b" * 64

def pair():
    return {"records": [
        {"account": account, "hwnd": hwnd, "pid": pid, "phase": "TEAM",
         "frame_hashes": [H1, H2], "session_id": "same", "reviewed": True}
        for account, hwnd, pid in [("main", 100, 200), ("alt", 101, 201)]
    ]}

class ReviewCliTests(unittest.TestCase):
    def test_reviewed_pair_never_enables_input(self):
        result = review_payload(pair())
        self.assertEqual(result["status"], "observed")
        self.assertFalse(result["input_enabled"])

    def test_unreviewed_pauses(self):
        p = pair()
        p["records"][0]["reviewed"] = False
        self.assertEqual(review_payload(p)["status"], "paused")

    def test_truthy_string_review_does_not_pass(self):
        p = pair()
        p["records"][0]["reviewed"] = "false"
        self.assertEqual(review_payload(p)["status"], "paused")

    def test_offline_review_never_claims_live_verification(self):
        self.assertFalse(review_payload(pair())["game_state_verified"])

    def test_conflicting_phase_pauses(self):
        p = pair()
        p["records"][1]["phase"] = "BATTLE"
        self.assertEqual(review_payload(p)["status"], "paused")

    def test_invalid_phase_pauses(self):
        p = pair()
        p["records"][0]["phase"] = "NOT_A_PHASE"
        self.assertEqual(review_payload(p)["reason"], "invalid_record")

    def test_bad_structure_pauses(self):
        self.assertEqual(review_payload({})["reason"], "invalid_payload")

    def test_duplicate_identity_pauses(self):
        p = pair()
        p["records"][1]["hwnd"] = 100
        self.assertEqual(review_payload(p)["status"], "paused")

if __name__ == "__main__":
    unittest.main()
