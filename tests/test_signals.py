import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from signals import extract_signals, pick_primary  # noqa: E402
from fit import score_lead  # noqa: E402
from qa import check  # noqa: E402

CAREERS = """Careers at Desert Door PM. We are looking for a full-time Bookkeeper to join our
team in Phoenix. Apply today. Also: Office Manager position available."""
HOMEPAGE = """Desert Door Property Management manages 1,250+ doors across the Valley.
Owners log in to the owner portal powered by AppFolio. Residents can pay rent online.
Late fees apply after the 5th; we handle delinquency. We send owner statements monthly."""
BARE = "Welcome to Smith Realty. Call us for all your real estate needs. Est. 1998. Suite 240."


class SignalTests(unittest.TestCase):
    def test_hiring_detected(self):
        types = {s.type for s in extract_signals(CAREERS, "https://x.test/careers")}
        self.assertIn("hiring", types)

    def test_scale_software_portal_late_rent(self):
        sigs = extract_signals(HOMEPAGE, "https://x.test/")
        types = {s.type for s in sigs}
        self.assertEqual({"scale", "software", "payment_portal", "late_rent", "finance_ops"}, types)
        doors = next(s.value for s in sigs if s.type == "scale")
        self.assertEqual("1250", doors)
        self.assertEqual("appfolio", next(s.value for s in sigs if s.type == "software"))

    def test_years_and_suite_numbers_are_not_doors(self):
        self.assertEqual([], extract_signals(BARE, "https://x.test/"))

    def test_generic_service_menu_is_not_a_signal(self):
        menu = "Services: Tenant Screening Rent Collection Maintenance Eviction. Call (602) 555-0100."
        self.assertEqual([], extract_signals(menu, "https://x.test/"))

    def test_phone_numbers_are_scrubbed_from_evidence(self):
        text = "Owner Login Call us now: (623) 302-6912 Home About"
        sig = extract_signals(text, "https://x.test/")[0]
        self.assertIn("[phone]", sig.evidence)
        self.assertNotIn("302-6912", sig.evidence)

    def test_priority_and_fallback(self):
        sigs = extract_signals(HOMEPAGE, "https://x.test/") + extract_signals(CAREERS, "https://x.test/careers")
        self.assertEqual("hiring", pick_primary(sigs, 4.5, 80, "maps").type)
        fb = pick_primary([], 4.2, 37, "https://maps.test")
        self.assertEqual("maps_only", fb.type)
        self.assertIn("4.2-star", fb.evidence)
        self.assertIn("37 Google reviews", fb.evidence)


class FitTests(unittest.TestCase):
    def test_bounds_and_reasons(self):
        score, reason = score_lead(signal_types={"hiring", "software", "late_rent"}, doors=1250, reviews=10, has_email=True, has_phone=True)
        self.assertEqual(5, score)
        self.assertIn("hiring", reason)
        score, reason = score_lead(signal_types=set(), doors=None, reviews=3, has_email=False, has_phone=False)
        self.assertEqual(1, score)


class QATests(unittest.TestCase):
    lead = {"signal_type": "scale", "doors_stated": "1250", "google_rating": "4.5", "google_reviews": "80", "business_name": "Desert Door", "city": "Phoenix", "state": "Arizona", "signal_evidence": "manages 1,250+ doors", "pm_software": ""}

    def test_clean_draft_passes(self):
        d = {"subject": "Owner statements for 1,250 doors", "opener": "Managing 1,250 doors means a lot of owner statements every month. Blaze closes the books and reconciles trust accounts without adding headcount. Worth a 15-minute look?"}
        self.assertEqual([], check(self.lead, d))

    def test_meeting_length_allowed_but_bare_number_not(self):
        ok = {"subject": "Owner statements for 1,250 doors", "opener": "You manage 1,250 doors. Blaze closes the books for you. Open to a 15-minute look?"}
        self.assertEqual([], check(self.lead, ok))
        bad = {"subject": "Owner statements for 1,250 doors", "opener": "You manage 1,250 doors and charge late fees after the 30th. Blaze closes the books for you."}
        self.assertIn("unsupported_number:30", check(self.lead, bad))

    def test_hallucinated_number_and_filler_flagged(self):
        d = {"subject": "Quick question!", "opener": "I hope this finds you well. You manage 3,000 doors across 12 offices, so Blaze could help."}
        flags = check(self.lead, d)
        self.assertTrue(any(f.startswith("unsupported_number:3000") for f in flags))
        self.assertTrue(any(f.startswith("unsupported_number:12") for f in flags))
        self.assertIn("exclamation", flags)
        self.assertIn("banned:hope this finds you well", flags)
        self.assertIn("signal_not_used", flags)


if __name__ == "__main__":
    unittest.main()
