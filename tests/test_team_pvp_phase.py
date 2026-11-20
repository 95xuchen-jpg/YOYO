import unittest
from team_pvp_phase import Phase, PvpObservation, TeamPvpTracker


def pair(phase=Phase.LOBBY, **kwargs):
    base = dict(identity_verified=True, two_frames_agree=True,
                geometry_ok=True, session_id="s1")
    base.update(kwargs)
    return (PvpObservation("main", phase, evidence_id="m", **base),
            PvpObservation("alt", phase, evidence_id="a", **base))


class TeamPvpPhaseTests(unittest.TestCase):
    def test_happy_path_stays_read_only(self):
        tracker = TeamPvpTracker()
        for phase in (Phase.LOBBY, Phase.TEAM, Phase.QUEUED,
                      Phase.MATCHED, Phase.BATTLE, Phase.RESULT):
            result = tracker.advance(pair(phase))
            self.assertEqual(result.status, "observed")
            self.assertFalse(result.input_enabled)

    def test_unknown_fails_closed(self):
        self.assertEqual(TeamPvpTracker().advance(pair(Phase.UNKNOWN)).reason,
                         "unverified_phase")

    def test_initial_battle_is_not_accepted(self):
        self.assertEqual(TeamPvpTracker().advance(pair(Phase.BATTLE)).reason,
                         "initial_lobby_not_verified")

    def test_cross_account_disagreement(self):
        main, alt = pair()
        alt = PvpObservation("alt", Phase.TEAM, True, True, True, "s1", "a")
        self.assertEqual(TeamPvpTracker().advance((main, alt)).reason,
                         "cross_account_phase_conflict")

    def test_session_mismatch(self):
        main, alt = pair()
        alt = PvpObservation("alt", Phase.LOBBY, True, True, True, "s2", "a")
        self.assertEqual(TeamPvpTracker().advance((main, alt)).reason,
                         "session_not_correlated")

    def test_no_image_evidence(self):
        self.assertEqual(TeamPvpTracker().advance(pair(two_frames_agree=False)).reason,
                         "insufficient_image_evidence")

    def test_duplicate_account(self):
        main, _ = pair()
        self.assertEqual(TeamPvpTracker().advance((main, main)).reason,
                         "exactly_two_explicit_accounts_required")

    def test_illegal_transition_does_not_advance(self):
        tracker = TeamPvpTracker()
        tracker.advance(pair())
        self.assertEqual(tracker.advance(pair(Phase.BATTLE)).reason,
                         "invalid_phase_transition")
        self.assertEqual(tracker.phase, Phase.LOBBY)

    def test_changed_session_pauses(self):
        tracker = TeamPvpTracker()
        tracker.advance(pair())
        self.assertEqual(tracker.advance(pair(session_id="s2")).reason,
                         "session_changed")


if __name__ == "__main__":
    unittest.main()
