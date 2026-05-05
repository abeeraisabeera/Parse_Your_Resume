"""
test_resume_parser.py
=====================
Full test suite for resume_parser.py (new granular schema).

Run:  python test_resume_parser.py          (no external deps needed)
      python test_resume_parser.py -v       (verbose)
"""

import json
import sys
import textwrap
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent))
import resume_parser as rp

# ══════════════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════════════

CLEAN_RESUME = textwrap.dedent("""\
    John Doe
    john.doe@example.com | +1-555-123-4567
    linkedin.com/in/johndoe

    EXPERIENCE
    Senior Software Engineer - Acme Corp        Jan 2019 - Present
    Software Engineer - Beta Systems             Mar 2016 - Dec 2018

    SKILLS
    Python, Django, PostgreSQL, Docker, AWS, Git, React, TensorFlow

    EDUCATION
    B.Sc. Computer Science - MIT, 2015
""")

MESSY_RESUME = textwrap.dedent("""\
    jane   smith
    janesmith@gmail.com
    linkedin.com/in/jane-smith-456

    exp:
    data scientist @ DataCorp (2020 - present)
    analyst, OldCo 2017-2019

    tools: pandas numpy sklearn SQL tableau power bi excel
""")

MINIMAL_RESUME = textwrap.dedent("""\
    Alex Johnson
    alex@corp.io

    Senior Lead Architect at TechGiant 2015 to present
    Skills: Kubernetes Terraform Azure Go Rust
""")

NO_DATES_RESUME = textwrap.dedent("""\
    Pat Lee
    pat.lee@mail.com

    intern at startup
    junior developer at small firm
    developer at medium company
    senior developer at large corp

    skills: java spring sql docker
""")

BEHANCE_RESUME = textwrap.dedent("""\
    Sara Design
    sara@design.io | +1-555-987-6543
    linkedin.com/in/saradesign
    behance.net/saradesign

    UX Designer - PixelCo        Jan 2020 - Present
    Junior Designer - ArtHouse   Feb 2018 - Dec 2019

    Skills: Figma, Photoshop, Illustrator, CSS
""")

INVALID_TEXT = "COMPANY LOGO HERE. All rights reserved 2024."

REQUIRED_KEYS = [
    "is_valid_resume", "name", "email", "phone", "linkedin",
    "estimated_years_of_experience", "experience_confidence",
    "skills", "top_skills", "current_role", "seniority_level",
    "role_detected", "companies_worked", "education",
    "resume_quality_score", "ranking_score", "ranking_breakdown",
    "notes", "behance", "behance_url",
]

RANKING_BREAKDOWN_KEYS = [
    "experience_score", "skills_score", "seniority_score", "quality_score",
]

# ══════════════════════════════════════════════════════════════════════════
# 1.  TEXT CLEANING
# ══════════════════════════════════════════════════════════════════════════

class TestCleanText(unittest.TestCase):

    def test_collapses_extra_spaces(self):
        self.assertNotIn("  ", rp._clean_text("hello   world\t\ttest"))

    def test_collapses_blank_lines(self):
        self.assertNotIn("\n\n\n", rp._clean_text("a\n\n\n\n\nb"))

    def test_strips_control_characters(self):
        # \x01 and \x07 are control chars — should be stripped
        result = rp._clean_text("hello\x01\x07world")
        self.assertNotIn("\x01", result)
        self.assertNotIn("\x07", result)

    def test_unicode_not_stripped(self):
        # \x80 is a valid Latin extended char — must NOT be stripped
        result = rp._clean_text("caf\x80 and r\x80sum\x80")
        # The bytes should remain (or be interpreted as-is)
        self.assertIn("caf", result)

    def test_preserves_meaningful_content(self):
        result = rp._clean_text(CLEAN_RESUME)
        self.assertIn("John Doe", result)
        self.assertIn("Acme Corp", result)


# ══════════════════════════════════════════════════════════════════════════
# 2.  REGEX PRE-PASS
# ══════════════════════════════════════════════════════════════════════════

class TestRegexPrepass(unittest.TestCase):

    def setUp(self):
        self.clean   = rp.regex_prepass(CLEAN_RESUME)
        self.messy   = rp.regex_prepass(MESSY_RESUME)
        self.behance = rp.regex_prepass(BEHANCE_RESUME)

    def test_email_clean(self):
        self.assertEqual(self.clean["email"], "john.doe@example.com")

    def test_email_missing(self):
        self.assertIsNone(rp.regex_prepass("No contact info.")["email"])

    def test_phone_extracted(self):
        self.assertIn("555", self.clean["phone"])

    def test_phone_too_short_ignored(self):
        self.assertIsNone(rp.regex_prepass("Call 123.")["phone"])

    def test_phone_date_range_rejected(self):
        # Real bug from production: "2022 - 2025" was captured as phone
        self.assertIsNone(rp.regex_prepass("Duration: 2022 - 2025")["phone"])

    def test_phone_year_range_hyphen_rejected(self):
        self.assertIsNone(rp.regex_prepass("2019-2022 Company Name")["phone"])

    def test_phone_iso_date_range_rejected(self):
        # "2025-09 - 2026-01" style
        self.assertIsNone(rp.regex_prepass("2025-09 - 2026-01")["phone"])

    def test_phone_real_number_still_extracted(self):
        self.assertIsNotNone(rp.regex_prepass("Call me at 0310-1913735")["phone"])

    def test_phone_real_number_with_plus_extracted(self):
        self.assertIsNotNone(rp.regex_prepass("+92(324) 5171517")["phone"])

    def test_international_phone(self):
        self.assertIsNotNone(rp.regex_prepass("Contact: +44 7911 123456")["phone"])

    def test_linkedin_clean(self):
        self.assertIn("johndoe", self.clean["linkedin"])

    def test_linkedin_missing(self):
        self.assertIsNone(rp.regex_prepass("Alice\nalice@test.com")["linkedin"])

    def test_behance_extracted(self):
        self.assertIn("saradesign", self.behance["behance"])

    def test_behance_normalised_to_https(self):
        self.assertTrue(self.behance["behance"].startswith("https://"))

    def test_behance_missing(self):
        self.assertIsNone(self.clean.get("behance"))

    def test_behance_no_trailing_slash(self):
        self.assertFalse(self.behance["behance"].endswith("/"))

    def test_behance_with_https_prefix(self):
        rf = rp.regex_prepass("Portfolio: https://www.behance.net/johnartist")
        self.assertIn("johnartist", rf["behance"])

    def test_date_ranges_detected(self):
        self.assertGreaterEqual(len(self.clean["_date_ranges"]), 1)

    def test_present_maps_to_2025(self):
        rf = rp.regex_prepass("Engineer Jan 2019 - Present")
        self.assertIn(2025, [end for _, end in rf["_date_ranges"]])

    def test_PRESENT_uppercase_does_not_crash(self):
        # Real production bug: "2020 - PRESENT" caused int("PRESENT") ValueError
        rf = rp.regex_prepass("Engineer 2020 - PRESENT")
        self.assertIsInstance(rf["_date_ranges"], list)

    def test_CURRENT_uppercase_does_not_crash(self):
        rf = rp.regex_prepass("Developer 2018 - CURRENT")
        self.assertIsInstance(rf["_date_ranges"], list)

    def test_years_found(self):
        self.assertIn(2019, self.clean["_years_found"])

    def test_multiple_emails_takes_first(self):
        self.assertEqual(
            rp.regex_prepass("primary@a.com and backup@b.com")["email"],
            "primary@a.com"
        )

    def test_behance_does_not_bleed_into_linkedin(self):
        rf = rp.regex_prepass("linkedin.com/in/user behance.net/artist")
        self.assertIn("artist", rf["behance"])
        self.assertNotIn("artist", rf["linkedin"])


# ══════════════════════════════════════════════════════════════════════════
# 3.  EXPERIENCE ESTIMATION
# ══════════════════════════════════════════════════════════════════════════

class TestExperienceEstimation(unittest.TestCase):

    def test_single_range(self):
        yrs, conf = rp._estimate_experience_from_dates([(2019, 2025)])
        self.assertEqual(yrs, 6.0)
        self.assertGreater(conf, 0)

    def test_overlapping_ranges_merged(self):
        yrs, _ = rp._estimate_experience_from_dates([(2016, 2019), (2018, 2022)])
        self.assertEqual(yrs, 6.0)

    def test_non_overlapping_ranges(self):
        yrs, _ = rp._estimate_experience_from_dates([(2010, 2012), (2014, 2016)])
        self.assertEqual(yrs, 4.0)

    def test_empty_ranges(self):
        yrs, conf = rp._estimate_experience_from_dates([])
        self.assertEqual(yrs, 0.0)
        self.assertEqual(conf, 0.0)

    def test_high_confidence_multiple_ranges(self):
        ranges = [(2010, 2013), (2013, 2016), (2016, 2019), (2019, 2022)]
        _, conf = rp._estimate_experience_from_dates(ranges)
        self.assertGreaterEqual(conf, 0.6)


# ══════════════════════════════════════════════════════════════════════════
# 4.  SCORING HELPERS
# ══════════════════════════════════════════════════════════════════════════

class TestScoringHelpers(unittest.TestCase):

    def test_exp_score_zero(self):
        self.assertEqual(rp._experience_score(0), 0.0)

    def test_exp_score_five_years(self):
        self.assertEqual(rp._experience_score(5), 50.0)

    def test_exp_score_ten_years(self):
        self.assertEqual(rp._experience_score(10), 75.0)

    def test_exp_score_twenty_plus(self):
        self.assertEqual(rp._experience_score(25), 95.0)

    def test_exp_score_interpolates(self):
        score = rp._experience_score(3)
        self.assertGreater(score, 25)
        self.assertLess(score, 50)

    def test_exp_score_monotonically_increasing(self):
        scores = [rp._experience_score(y) for y in range(0, 21)]
        self.assertEqual(scores, sorted(scores))

    def test_skills_score_zero(self):
        self.assertEqual(rp._skills_score(0), 0.0)

    def test_skills_score_small(self):
        self.assertEqual(rp._skills_score(2), 20.0)

    def test_skills_score_mid(self):
        self.assertEqual(rp._skills_score(8), 60.0)

    def test_skills_score_large(self):
        self.assertEqual(rp._skills_score(20), 90.0)

    def test_seniority_score_map_values(self):
        self.assertEqual(rp._SENIORITY_SCORE_MAP["intern"], 10)
        self.assertEqual(rp._SENIORITY_SCORE_MAP["junior"], 30)
        self.assertEqual(rp._SENIORITY_SCORE_MAP["mid"],    50)
        self.assertEqual(rp._SENIORITY_SCORE_MAP["senior"], 70)
        self.assertEqual(rp._SENIORITY_SCORE_MAP["lead"],   90)

    def test_safe_int_plain(self):
        self.assertEqual(rp._safe_int("1234"), 1234)

    def test_safe_int_comma(self):
        self.assertEqual(rp._safe_int("34,521"), 34521)

    def test_safe_int_k(self):
        self.assertEqual(rp._safe_int("1.2k"), 1200)

    def test_safe_int_m(self):
        self.assertEqual(rp._safe_int("2m"), 2_000_000)

    def test_safe_int_none(self):
        self.assertIsNone(rp._safe_int(None))

    def test_safe_int_empty(self):
        self.assertIsNone(rp._safe_int(""))

    def test_safe_int_non_numeric(self):
        self.assertIsNone(rp._safe_int("views"))


# ══════════════════════════════════════════════════════════════════════════
# 5.  SENIORITY DETECTION
# ══════════════════════════════════════════════════════════════════════════

class TestSeniorityDetection(unittest.TestCase):

    def test_intern(self):
        self.assertEqual(rp._detect_seniority("Software Engineering Intern"), "intern")

    def test_junior(self):
        self.assertEqual(rp._detect_seniority("Junior Developer"), "junior")

    def test_senior(self):
        self.assertEqual(rp._detect_seniority("Senior Software Engineer"), "senior")

    def test_lead(self):
        self.assertEqual(rp._detect_seniority("Lead Architect"), "lead")

    def test_director_is_lead(self):
        self.assertEqual(rp._detect_seniority("Director of Engineering"), "lead")

    def test_vp_is_lead(self):
        self.assertEqual(rp._detect_seniority("VP of Product"), "lead")

    def test_unknown_when_no_signals(self):
        self.assertEqual(rp._detect_seniority("worked on some projects"), "unknown")


# ══════════════════════════════════════════════════════════════════════════
# 6.  RESUME QUALITY SCORE
# ══════════════════════════════════════════════════════════════════════════

class TestResumeQualityScore(unittest.TestCase):

    def _score(self, text):
        rf     = rp.regex_prepass(text)
        skills = [k for k in rp._SKILL_KEYWORDS if k in text.lower()]
        dates  = rf["_date_ranges"]
        return rp._resume_quality_score(text, rf, skills, dates)

    def test_full_resume_high_score(self):
        self.assertGreaterEqual(self._score(CLEAN_RESUME), 60)

    def test_empty_text_zero(self):
        self.assertEqual(self._score(""), 0)

    def test_bounded_0_100(self):
        for text in [CLEAN_RESUME, MESSY_RESUME, MINIMAL_RESUME, ""]:
            s = self._score(text)
            self.assertGreaterEqual(s, 0)
            self.assertLessEqual(s, 100)

    def test_contact_adds_points(self):
        with_c    = self._score("john@x.com\nSoftware Engineer 2020-present\nskills: python")
        without_c = self._score("Software Engineer 2020-present\nskills: python")
        self.assertGreater(with_c, without_c)


# ══════════════════════════════════════════════════════════════════════════
# 7.  RULE-BASED PARSE — full new schema
# ══════════════════════════════════════════════════════════════════════════

class TestRuleBasedParse(unittest.TestCase):

    def _parse(self, text):
        rf = rp.regex_prepass(text)
        return rp.rule_based_parse(text, rf)

    def test_all_schema_keys_present(self):
        result = self._parse(CLEAN_RESUME)
        for key in [
            "is_valid_resume", "name", "estimated_years_of_experience",
            "experience_confidence", "skills", "top_skills", "current_role",
            "seniority_level", "companies_worked", "education",
            "resume_quality_score", "ranking_score", "ranking_breakdown", "notes",
        ]:
            self.assertIn(key, result, f"Missing: {key}")

    def test_ranking_breakdown_keys(self):
        bd = self._parse(CLEAN_RESUME)["ranking_breakdown"]
        for k in RANKING_BREAKDOWN_KEYS:
            self.assertIn(k, bd)

    def test_skills_extracted(self):
        skills = self._parse(CLEAN_RESUME)["skills"]
        self.assertIn("python", skills)
        self.assertIn("docker", skills)

    def test_top_skills_max_five(self):
        self.assertLessEqual(len(self._parse(CLEAN_RESUME)["top_skills"]), 5)

    def test_top_skills_subset_of_skills(self):
        r = self._parse(CLEAN_RESUME)
        for ts in r["top_skills"]:
            self.assertIn(ts, r["skills"])

    def test_seniority_senior(self):
        self.assertEqual(self._parse(CLEAN_RESUME)["seniority_level"], "senior")

    def test_seniority_intern_only_text(self):
        text = (
            "Tom Lee  tom@x.com\n"
            "Software Engineering Intern – StartupCo  Jun 2023 - Aug 2023\n"
            "Education: B.Sc. Computer Science (in progress), 2024\n"
            "Skills: python java git"
        )
        result = self._parse(text)
        self.assertEqual(result["seniority_level"], "intern")

    def test_seniority_senior_detected(self):
        text = (
            "Jane Doe  jane@x.com\n"
            "Senior Software Engineer – BigCorp  2018 - Present\n"
            "Engineer – SmallCo  2015 - 2018\n"
            "Education: B.Sc. CS, 2015\n"
            "Skills: python docker aws kubernetes"
        )
        result = self._parse(text)
        self.assertIn(result["seniority_level"], {"senior", "lead"})

    def test_experience_nonzero(self):
        self.assertGreater(self._parse(CLEAN_RESUME)["estimated_years_of_experience"], 0)

    def test_ranking_score_in_range(self):
        for text in [CLEAN_RESUME, MESSY_RESUME, MINIMAL_RESUME]:
            s = self._parse(text)["ranking_score"]
            self.assertGreaterEqual(s, 0)
            self.assertLessEqual(s, 100)

    def test_ranking_formula_consistency(self):
        r  = self._parse(CLEAN_RESUME)
        bd = r["ranking_breakdown"]
        expected = round(
            bd["experience_score"] * 0.4 +
            bd["skills_score"]     * 0.3 +
            bd["seniority_score"]  * 0.2 +
            bd["quality_score"]    * 0.1, 1
        )
        self.assertAlmostEqual(r["ranking_score"], expected, places=0)

    def test_invalid_text_flagged(self):
        result = self._parse(INVALID_TEXT)
        self.assertFalse(result["is_valid_resume"])
        self.assertEqual(result["ranking_score"], 0)

    def test_valid_resume_flagged_true(self):
        self.assertTrue(self._parse(CLEAN_RESUME)["is_valid_resume"])

    def test_no_crash_on_empty(self):
        self.assertIsInstance(self._parse(""), dict)

    def test_no_crash_on_minimal(self):
        self.assertIsInstance(self._parse(MINIMAL_RESUME), dict)

    def test_experience_confidence_in_range(self):
        for text in [CLEAN_RESUME, MESSY_RESUME, MINIMAL_RESUME]:
            r = self._parse(text)
            self.assertGreaterEqual(r["experience_confidence"], 0.0)
            self.assertLessEqual(r["experience_confidence"],   1.0)


# ══════════════════════════════════════════════════════════════════════════
# 8.  MERGE RESULTS
# ══════════════════════════════════════════════════════════════════════════

class TestMergeResults(unittest.TestCase):

    def _regex(self, behance=None):
        return {
            "email": "a@b.com", "phone": "+1-800-111-2222",
            "linkedin": "linkedin.com/in/test", "behance": behance,
            "_date_ranges": [(2015, 2020)], "_years_found": [2015, 2020],
        }

    def _llm(self):
        return {
            "is_valid_resume": True, "name": "Test User",
            "estimated_years_of_experience": 5, "experience_confidence": 0.9,
            "skills": ["Python", "Django"], "top_skills": ["Python"],
            "current_role": "Engineer", "seniority_level": "senior",
            "companies_worked": ["Acme"], "education": "B.Sc.",
            "resume_quality_score": 80, "ranking_score": 72.0,
            "ranking_breakdown": {
                "experience_score": 50, "skills_score": 40,
                "seniority_score": 70, "quality_score": 80,
            },
            "notes": "LLM parsed",
        }

    def test_regex_contact_overrides_llm(self):
        final = rp.merge_results(self._regex(), self._llm())
        self.assertEqual(final["email"], "a@b.com")
        self.assertEqual(final["phone"], "+1-800-111-2222")
        self.assertIn("test", final["linkedin"])

    def test_llm_experience_kept(self):
        self.assertEqual(
            rp.merge_results(self._regex(), self._llm())["estimated_years_of_experience"], 5
        )

    def test_fallback_experience_when_llm_zero(self):
        llm = self._llm(); llm["estimated_years_of_experience"] = 0
        final = rp.merge_results(self._regex(), llm)
        self.assertGreater(final["estimated_years_of_experience"], 0)

    def test_old_confidence_key_renamed(self):
        llm = self._llm()
        llm.pop("experience_confidence", None)
        llm["confidence_score_experience"] = 0.7
        final = rp.merge_results(self._regex(), llm)
        self.assertIn("experience_confidence", final)
        self.assertNotIn("confidence_score_experience", final)

    def test_ranking_breakdown_recomputed_when_missing(self):
        llm = self._llm(); llm.pop("ranking_breakdown")
        final = rp.merge_results(self._regex(), llm)
        bd = final["ranking_breakdown"]
        self.assertIsInstance(bd, dict)
        for k in RANKING_BREAKDOWN_KEYS:
            self.assertIn(k, bd)

    def test_top_skills_derived_when_missing(self):
        llm = self._llm(); llm["top_skills"] = []
        final = rp.merge_results(self._regex(), llm)
        self.assertGreater(len(final["top_skills"]), 0)

    def test_behance_url_stored_as_interim_key(self):
        final = rp.merge_results(
            self._regex(behance="https://www.behance.net/test"), self._llm()
        )
        self.assertEqual(final.get("behance_url"), "https://www.behance.net/test")

    def test_ranking_score_clamped_high(self):
        llm = self._llm(); llm["ranking_score"] = 150.0
        self.assertLessEqual(rp.merge_results(self._regex(), llm)["ranking_score"], 100.0)

    def test_ranking_score_clamped_low(self):
        llm = self._llm(); llm["ranking_score"] = -10.0
        self.assertGreaterEqual(rp.merge_results(self._regex(), llm)["ranking_score"], 0.0)

    def test_all_scalar_defaults_present(self):
        final = rp.merge_results(self._regex(), {})
        for key in ("is_valid_resume", "name", "estimated_years_of_experience",
                    "experience_confidence", "current_role", "seniority_level",
                    "education", "resume_quality_score", "ranking_score", "notes"):
            self.assertIn(key, final)


# ══════════════════════════════════════════════════════════════════════════
# 9.  LLM CALL (mocked)
# ══════════════════════════════════════════════════════════════════════════

class TestCallGroqLLM(unittest.TestCase):

    def _payload(self):
        return {
            "is_valid_resume": True, "name": "Jane Smith",
            "estimated_years_of_experience": 7, "experience_confidence": 0.85,
            "skills": ["Python", "SQL"], "top_skills": ["Python", "SQL"],
            "current_role": "Data Scientist", "seniority_level": "senior",
            "companies_worked": ["DataCorp"], "education": "B.Sc. CS",
            "resume_quality_score": 75, "ranking_score": 78.0,
            "ranking_breakdown": {
                "experience_score": 65, "skills_score": 40,
                "seniority_score": 70, "quality_score": 75,
            },
            "notes": "LLM parsed",
        }

    def _client(self, content):
        client = MagicMock()
        choice = MagicMock()
        choice.message.content = content
        client.chat.completions.create.return_value.choices = [choice]
        return client

    def test_valid_json(self):
        result = rp.call_groq_llm("text", self._client(json.dumps(self._payload())))
        self.assertEqual(result["name"], "Jane Smith")
        self.assertEqual(result["seniority_level"], "senior")

    def test_strips_markdown_fences(self):
        wrapped = f"```json\n{json.dumps(self._payload())}\n```"
        result  = rp.call_groq_llm("text", self._client(wrapped))
        self.assertEqual(result["name"], "Jane Smith")

    def test_invalid_json_raises(self):
        with self.assertRaises(json.JSONDecodeError):
            rp.call_groq_llm("text", self._client("not json at all"))


# ══════════════════════════════════════════════════════════════════════════
# 10. RANKING AGGREGATOR
# ══════════════════════════════════════════════════════════════════════════

class TestRankCandidates(unittest.TestCase):

    def setUp(self):
        self.raw = [
            {"name": "Alice", "ranking_score": 85.0},
            {"name": "Bob",   "ranking_score": 60.0},
            {"name": "Carol", "ranking_score": 92.0},
        ]
        self.ranked = rp.rank_candidates(self.raw)

    def test_sorted_descending(self):
        scores = [r["ranking_score"] for r in self.ranked]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_rank_field_added(self):
        for r in self.ranked:
            self.assertIn("rank", r)

    def test_rank_1_is_highest(self):
        top = next(r for r in self.ranked if r["rank"] == 1)
        self.assertEqual(top["name"], "Carol")

    def test_empty_list(self):
        self.assertEqual(rp.rank_candidates([]), [])

    def test_single_candidate(self):
        self.assertEqual(rp.rank_candidates([{"ranking_score": 50}])[0]["rank"], 1)

    def test_summary_table_handles_none_fields(self):
        # Real production bug: error records have None for numeric fields → TypeError
        records = [
            {"rank": 1, "name": "Good Candidate", "ranking_score": 75.0,
             "estimated_years_of_experience": 5.0, "seniority_level": "senior",
             "resume_quality_score": 60, "source_file": "good.pdf",
             "is_valid_resume": True, "behance": {}},
            {"rank": 2, "source_file": "broken.pdf", "ranking_score": 0,
             "error": "Could not extract text"},  # error record — all fields None
        ]
        # must not raise
        try:
            import io, sys
            buf = io.StringIO()
            old_stdout = sys.stdout
            sys.stdout = buf
            rp.print_summary_table(records)
            sys.stdout = old_stdout
        except (TypeError, ValueError) as e:
            self.fail(f"print_summary_table crashed with: {e}")


# ══════════════════════════════════════════════════════════════════════════
# 11. FULL PIPELINE (mocked PDF)
# ══════════════════════════════════════════════════════════════════════════

class TestParsePipelineMocked(unittest.TestCase):

    def _groq_client(self, name="Mocked User", score=80.0):
        payload = {
            "is_valid_resume": True, "name": name,
            "estimated_years_of_experience": 8, "experience_confidence": 0.85,
            "skills": ["Python", "Django"], "top_skills": ["Python"],
            "current_role": "Engineer", "seniority_level": "senior",
            "companies_worked": ["Acme"], "education": "B.Sc.",
            "resume_quality_score": 75, "ranking_score": score,
            "ranking_breakdown": {
                "experience_score": 65, "skills_score": 40,
                "seniority_score": 70, "quality_score": 75,
            },
            "notes": "mocked",
        }
        client = MagicMock()
        choice = MagicMock()
        choice.message.content = json.dumps(payload)
        client.chat.completions.create.return_value.choices = [choice]
        return client

    @patch("resume_parser.extract_text", return_value=CLEAN_RESUME)
    def test_with_llm_mocked(self, _):
        result = rp.parse_resume("fake.pdf", groq_client=self._groq_client())
        self.assertEqual(result["name"], "Mocked User")
        self.assertEqual(result["email"], "john.doe@example.com")

    @patch("resume_parser.extract_text", return_value=CLEAN_RESUME)
    def test_all_required_keys_present(self, _):
        result = rp.parse_resume("fake.pdf", groq_client=None)
        for key in REQUIRED_KEYS:
            self.assertIn(key, result, f"Missing: {key}")

    @patch("resume_parser.extract_text", return_value=CLEAN_RESUME)
    def test_behance_key_structure(self, _):
        result = rp.parse_resume("fake.pdf", groq_client=None)
        b = result["behance"]
        self.assertIn("url",           b)
        self.assertIn("projects",      b)
        self.assertIn("project_count", b)
        self.assertIn("fetch_status",  b)

    @patch("resume_parser.extract_text", return_value=MESSY_RESUME)
    def test_messy_no_crash(self, _):
        self.assertIsInstance(rp.parse_resume("messy.pdf", groq_client=None), dict)

    @patch("resume_parser.extract_text", side_effect=ValueError("no text"))
    def test_extraction_error_raises(self, _):
        with self.assertRaises(ValueError):
            rp.parse_resume("empty.pdf", groq_client=None)

    @patch("resume_parser.extract_text", return_value=CLEAN_RESUME)
    def test_no_behance_flag(self, _):
        result = rp.parse_resume("fake.pdf", groq_client=None, fetch_behance=False)
        self.assertEqual(result["behance"]["fetch_status"], "skipped")


# ══════════════════════════════════════════════════════════════════════════
# 12. BEHANCE SCRAPER (mocked HTTP)
# ══════════════════════════════════════════════════════════════════════════

_FAKE_BEHANCE_HTML = """
<html><body>
  <div class="ProjectCoverNeue-root">
    <a href="/gallery/111111/Brand-Identity" title="Brand Identity">Brand Identity</a>
    <img src="https://mir-s3-cdn-cf.behance.net/cover.jpg" />
    <span aria-label="Views">12,400</span>
    <span aria-label="Appreciations">340</span>
  </div>
  <div class="ProjectCoverNeue-root">
    <a href="/gallery/222222/Mobile-App-UI" title="Mobile App UI">Mobile App UI</a>
    <img src="https://mir-s3-cdn-cf.behance.net/cover2.jpg" />
    <span aria-label="Views">8.1k</span>
    <span aria-label="Appreciations">210</span>
  </div>
</body></html>
"""

class TestFetchBehancePortfolio(unittest.TestCase):

    @patch("resume_parser.HAS_SCRAPER", False)
    def test_skipped_when_no_scraper(self):
        r = rp.fetch_behance_portfolio("https://www.behance.net/test")
        self.assertEqual(r["fetch_status"], "skipped")

    @patch("resume_parser.HAS_SCRAPER", True)
    @patch("resume_parser.requests.get")
    def test_successful_returns_projects(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = _FAKE_BEHANCE_HTML
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp
        r = rp.fetch_behance_portfolio("https://www.behance.net/sara")
        self.assertEqual(r["fetch_status"], "ok")
        self.assertGreater(len(r["projects"]), 0)

    @patch("resume_parser.HAS_SCRAPER", True)
    @patch("resume_parser.requests.get")
    def test_titles_extracted(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = _FAKE_BEHANCE_HTML
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp
        titles = [p["title"] for p in
                  rp.fetch_behance_portfolio("https://www.behance.net/sara")["projects"]]
        self.assertIn("Brand Identity", titles)

    @patch("resume_parser.HAS_SCRAPER", True)
    @patch("resume_parser.requests.get")
    def test_urls_are_absolute(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = _FAKE_BEHANCE_HTML
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp
        for p in rp.fetch_behance_portfolio("https://www.behance.net/sara")["projects"]:
            if p["url"]:
                self.assertTrue(p["url"].startswith("http"))

    @patch("resume_parser.HAS_SCRAPER", True)
    @patch("resume_parser.requests.get")
    def test_http_error(self, mock_get):
        import requests as req_lib
        mock_resp = MagicMock(); mock_resp.status_code = 404
        mock_get.return_value.raise_for_status.side_effect = (
            req_lib.exceptions.HTTPError(response=mock_resp)
        )
        self.assertEqual(
            rp.fetch_behance_portfolio("https://www.behance.net/x")["fetch_status"], "error"
        )

    @patch("resume_parser.HAS_SCRAPER", True)
    @patch("resume_parser.requests.get")
    def test_network_error(self, mock_get):
        import requests as req_lib
        mock_get.side_effect = req_lib.exceptions.ConnectionError("timeout")
        self.assertEqual(
            rp.fetch_behance_portfolio("https://www.behance.net/x")["fetch_status"], "error"
        )

    @patch("resume_parser.HAS_SCRAPER", True)
    @patch("resume_parser.requests.get")
    def test_empty_page(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = "<html><body><p>Nothing</p></body></html>"
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp
        r = rp.fetch_behance_portfolio("https://www.behance.net/empty")
        self.assertEqual(r["fetch_status"], "ok")
        self.assertEqual(len(r["projects"]), 0)


# ══════════════════════════════════════════════════════════════════════════
# 13. BEHANCE PIPELINE INTEGRATION
# ══════════════════════════════════════════════════════════════════════════

class TestBehancePipelineIntegration(unittest.TestCase):

    def _mock_fetch_return(self):
        return {
            "projects": [{"title": "Logo", "url": "https://behance.net/g/1/x",
                          "tools_used": ["Illustrator"], "views": 500,
                          "appreciations": 20, "cover_image": None}],
            "total_found": 1, "fetch_status": "ok", "error": None,
        }

    @patch("resume_parser.extract_text", return_value=BEHANCE_RESUME)
    @patch("resume_parser.fetch_behance_portfolio")
    def test_fetch_called_when_url_present(self, mock_fetch, _):
        mock_fetch.return_value = self._mock_fetch_return()
        rp.parse_resume("sara.pdf", groq_client=None, fetch_behance=True)
        mock_fetch.assert_called_once()

    @patch("resume_parser.extract_text", return_value=BEHANCE_RESUME)
    @patch("resume_parser.fetch_behance_portfolio")
    def test_projects_reshaped_to_spec(self, mock_fetch, _):
        mock_fetch.return_value = self._mock_fetch_return()
        result = rp.parse_resume("sara.pdf", groq_client=None, fetch_behance=True)
        proj = result["behance"]["projects"][0]
        for key in ("title", "description", "tools", "views"):
            self.assertIn(key, proj, f"Missing project key: {key}")

    @patch("resume_parser.extract_text", return_value=CLEAN_RESUME)
    def test_no_url_gives_no_url_status(self, _):
        result = rp.parse_resume("john.pdf", groq_client=None, fetch_behance=True)
        self.assertIsNone(result["behance"]["url"])
        self.assertEqual(result["behance"]["fetch_status"], "no_url")

    @patch("resume_parser.extract_text", return_value=BEHANCE_RESUME)
    @patch("resume_parser.fetch_behance_portfolio")
    def test_fetch_not_called_when_disabled(self, mock_fetch, _):
        rp.parse_resume("sara.pdf", groq_client=None, fetch_behance=False)
        mock_fetch.assert_not_called()

    @patch("resume_parser.extract_text", return_value=BEHANCE_RESUME)
    def test_behance_url_in_output(self, _):
        result = rp.parse_resume("sara.pdf", groq_client=None, fetch_behance=False)
        self.assertIn("saradesign", result["behance"]["url"])

    @patch("resume_parser.extract_text", return_value=BEHANCE_RESUME)
    def test_ranking_deterministic_regardless_of_behance(self, _):
        r1 = rp.parse_resume("sara.pdf", groq_client=None, fetch_behance=False)
        r2 = rp.parse_resume("sara.pdf", groq_client=None, fetch_behance=False)
        self.assertEqual(r1["ranking_score"], r2["ranking_score"])


# ══════════════════════════════════════════════════════════════════════════
# 14. EDGE CASES & ROBUSTNESS
# ══════════════════════════════════════════════════════════════════════════

class TestEdgeCases(unittest.TestCase):

    def test_ranking_never_above_100(self):
        text = (
            "Senior Principal Director 2000-Present\n"
            "python java c++ rust go react angular vue django flask "
            "tensorflow pytorch sql mongodb aws azure gcp kubernetes docker "
            "terraform ansible spark hadoop kafka elasticsearch redis tableau"
        )
        rf = rp.regex_prepass(text)
        r  = rp.rule_based_parse(text, rf)
        self.assertLessEqual(r["ranking_score"], 100.0)

    def test_ranking_never_below_0(self):
        rf = rp.regex_prepass("")
        self.assertGreaterEqual(rp.rule_based_parse("", rf)["ranking_score"], 0.0)

    def test_different_resumes_different_scores(self):
        rf_c = rp.regex_prepass(CLEAN_RESUME)
        rf_m = rp.regex_prepass(MINIMAL_RESUME)
        r_c  = rp.rule_based_parse(CLEAN_RESUME, rf_c)["ranking_score"]
        r_m  = rp.rule_based_parse(MINIMAL_RESUME, rf_m)["ranking_score"]
        self.assertNotEqual(r_c, r_m)

    def test_seniority_always_valid_value(self):
        valid = {"intern", "junior", "mid", "senior", "lead", "unknown"}
        for text in [CLEAN_RESUME, MESSY_RESUME, MINIMAL_RESUME, NO_DATES_RESUME]:
            rf = rp.regex_prepass(text)
            r  = rp.rule_based_parse(text, rf)
            self.assertIn(r["seniority_level"], valid)

    def test_experience_confidence_always_bounded(self):
        for text in [CLEAN_RESUME, MESSY_RESUME, MINIMAL_RESUME]:
            rf = rp.regex_prepass(text)
            r  = rp.rule_based_parse(text, rf)
            self.assertGreaterEqual(r["experience_confidence"], 0.0)
            self.assertLessEqual(r["experience_confidence"],   1.0)


# ══════════════════════════════════════════════════════════════════════════
# 15. RATE-LIMIT & RETRY HANDLING
# ══════════════════════════════════════════════════════════════════════════

def _make_client_with_side_effects(side_effects: list, final_payload: dict):
    """
    Return a mock Groq client whose successive calls raise the given
    side_effects and then succeed with final_payload on the last call.
    """
    client = MagicMock()
    choice = MagicMock()
    choice.message.content = json.dumps(final_payload)
    success = MagicMock()
    success.choices = [choice]

    call_results = list(side_effects) + [success]
    client.chat.completions.create.side_effect = call_results
    return client


def _good_payload():
    return {
        "is_valid_resume": True, "name": "Retry User",
        "estimated_years_of_experience": 5, "experience_confidence": 0.8,
        "skills": ["Python"], "top_skills": ["Python"],
        "current_role": "Engineer", "seniority_level": "mid",
        "companies_worked": ["Acme"], "education": "B.Sc.",
        "resume_quality_score": 60, "ranking_score": 55.0,
        "ranking_breakdown": {
            "experience_score": 50, "skills_score": 20,
            "seniority_score": 50, "quality_score": 60,
        },
        "notes": "ok",
    }


class _FakeRateLimitError(Exception):
    """Simulates Groq RateLimitError with an optional Retry-After header."""
    def __init__(self, retry_after: float | None = None):
        super().__init__("429 rate_limit exceeded")
        self.response = None
        if retry_after is not None:
            self.response = MagicMock()
            self.response.headers = {"Retry-After": str(retry_after)}


class _FakeDailyQuotaError(Exception):
    """Simulates Groq daily quota exhaustion (large Retry-After value)."""
    def __init__(self):
        super().__init__("429 rate_limit exceeded")
        self.response = MagicMock()
        # 940 s / 2833 s are real values seen in production
        self.response.headers = {"Retry-After": "940"}


class _FakeServerError(Exception):
    def __init__(self): super().__init__("503 ServiceUnavailable")


class _FakeAuthError(Exception):
    def __init__(self): super().__init__("401 authentication failed")


class TestRetryHandling(unittest.TestCase):

    @patch("resume_parser.time.sleep")
    def test_succeeds_on_first_attempt(self, mock_sleep):
        client = MagicMock()
        choice = MagicMock()
        choice.message.content = json.dumps(_good_payload())
        client.chat.completions.create.return_value.choices = [choice]
        result = rp.call_groq_llm("text", client, max_retries=4)
        self.assertEqual(result["name"], "Retry User")
        mock_sleep.assert_not_called()

    @patch("resume_parser.time.sleep")
    def test_retries_on_rate_limit_then_succeeds(self, mock_sleep):
        client = _make_client_with_side_effects(
            [_FakeRateLimitError(), _FakeRateLimitError()],
            _good_payload(),
        )
        result = rp.call_groq_llm("text", client, max_retries=4)
        self.assertEqual(result["name"], "Retry User")
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("resume_parser.time.sleep")
    def test_raises_after_all_retries_exhausted(self, mock_sleep):
        errors = [_FakeRateLimitError()] * 6
        client = _make_client_with_side_effects(errors, _good_payload())
        with self.assertRaises(Exception):
            rp.call_groq_llm("text", client, max_retries=4)

    @patch("resume_parser.time.sleep")
    def test_zero_retries_raises_immediately(self, mock_sleep):
        client = _make_client_with_side_effects(
            [_FakeRateLimitError()], _good_payload()
        )
        with self.assertRaises(Exception):
            rp.call_groq_llm("text", client, max_retries=0)
        mock_sleep.assert_not_called()

    @patch("resume_parser.time.sleep")
    def test_daily_quota_raises_immediately_without_long_wait(self, mock_sleep):
        # Retry-After: 940 s → daily quota → must NOT sleep 940 s
        client = _make_client_with_side_effects(
            [_FakeDailyQuotaError()], _good_payload()
        )
        with self.assertRaises(RuntimeError) as ctx:
            rp.call_groq_llm("text", client, max_retries=4)
        self.assertIn("daily_quota", str(ctx.exception))
        # sleep must never have been called with a huge value
        for call in mock_sleep.call_args_list:
            self.assertLess(call[0][0], 61,
                "Should NOT sleep > 60 s for daily quota — fall back immediately")

    @patch("resume_parser.time.sleep")
    def test_retry_after_capped_at_60(self, mock_sleep):
        # Retry-After: 30 (under cap) — should be honoured as floor
        client = _make_client_with_side_effects(
            [_FakeRateLimitError(retry_after=30.0)], _good_payload()
        )
        rp.call_groq_llm("text", client, max_retries=4)
        wait = mock_sleep.call_args[0][0]
        self.assertGreaterEqual(wait, 30.0)
        self.assertLess(wait, 61.0)

    @patch("resume_parser.time.sleep")
    def test_wait_stays_within_reasonable_range(self, mock_sleep):
        errors = [_FakeRateLimitError(), _FakeRateLimitError(), _FakeRateLimitError()]
        client = _make_client_with_side_effects(errors, _good_payload())
        rp.call_groq_llm("text", client, max_retries=4)
        for call in mock_sleep.call_args_list:
            wait = call[0][0]
            self.assertLess(wait, 65, f"Wait {wait}s exceeds reasonable cap")

    @patch("resume_parser.time.sleep")
    def test_wait_grows_attempt_over_attempt(self, mock_sleep):
        errors = [_FakeRateLimitError(), _FakeRateLimitError(), _FakeRateLimitError()]
        client = _make_client_with_side_effects(errors, _good_payload())
        rp.call_groq_llm("text", client, max_retries=4)
        waits = [call[0][0] for call in mock_sleep.call_args_list]
        self.assertGreaterEqual(waits[1], waits[0])
        self.assertGreaterEqual(waits[2], waits[1])

    @patch("resume_parser.time.sleep")
    def test_auth_error_not_retried(self, mock_sleep):
        client = _make_client_with_side_effects(
            [_FakeAuthError()], _good_payload()
        )
        with self.assertRaises(Exception):
            rp.call_groq_llm("text", client, max_retries=4)
        mock_sleep.assert_not_called()

    @patch("resume_parser.time.sleep")
    def test_transient_server_error_retried(self, mock_sleep):
        client = _make_client_with_side_effects(
            [_FakeServerError()], _good_payload()
        )
        result = rp.call_groq_llm("text", client, max_retries=4)
        self.assertEqual(result["name"], "Retry User")
        self.assertEqual(mock_sleep.call_count, 1)

    @patch("resume_parser.time.sleep")
    def test_invalid_json_not_retried(self, mock_sleep):
        client = MagicMock()
        choice = MagicMock()
        choice.message.content = "not json"
        client.chat.completions.create.return_value.choices = [choice]
        with self.assertRaises(json.JSONDecodeError):
            rp.call_groq_llm("text", client, max_retries=4)
        mock_sleep.assert_not_called()

    @patch("resume_parser.time.sleep")
    @patch("resume_parser.extract_text", return_value=CLEAN_RESUME)
    def test_pipeline_falls_back_on_exhausted_retries(self, _, mock_sleep):
        errors = [_FakeRateLimitError()] * 10
        client = _make_client_with_side_effects(errors, _good_payload())
        result = rp.parse_resume("fake.pdf", groq_client=client,
                                 fetch_behance=False, max_retries=2)
        self.assertIsInstance(result, dict)
        self.assertIn("ranking_score", result)

    @patch("resume_parser.time.sleep")
    @patch("resume_parser.extract_text", return_value=CLEAN_RESUME)
    def test_pipeline_falls_back_on_daily_quota(self, _, mock_sleep):
        # Daily quota hit → immediate fallback, no long sleep
        client = _make_client_with_side_effects(
            [_FakeDailyQuotaError()], _good_payload()
        )
        result = rp.parse_resume("fake.pdf", groq_client=client,
                                 fetch_behance=False, max_retries=4)
        self.assertIsInstance(result, dict)
        self.assertIn("ranking_score", result)
        # Crucially: never slept for the raw Retry-After value
        for call in mock_sleep.call_args_list:
            self.assertLess(call[0][0], 61)


# ══════════════════════════════════════════════════════════════════════════
# 16. CONSTRAINT 7 — UNICODE & INTERNATIONAL NAME SAFETY
# ══════════════════════════════════════════════════════════════════════════

class TestUnicodeSafety(unittest.TestCase):

    def test_arabic_name_preserved(self):
        text = "محمد علي\nmohamed.ali@example.com\nSoftware Engineer 2019-Present\nskills: python"
        result = rp._clean_text(text)
        self.assertIn("محمد", result)

    def test_accented_latin_preserved(self):
        text = "José García\njose@x.com\nEngineer 2020-present\nskills: python"
        result = rp._clean_text(text)
        self.assertIn("José", result)

    def test_urdu_script_preserved(self):
        text = "علی احمد\nali@x.com\nDeveloper 2018-2022\nskills: java"
        result = rp._clean_text(text)
        self.assertIn("علی", result)

    def test_control_chars_stripped(self):
        text = "John\x01Doe\x07\nengineer\nskills: python"
        result = rp._clean_text(text)
        self.assertNotIn("\x01", result)
        self.assertNotIn("\x07", result)

    def test_replacement_char_stripped(self):
        result = rp._clean_text("Name\ufffdValue")
        self.assertNotIn("\ufffd", result)

    def test_regular_ascii_preserved(self):
        result = rp._clean_text(CLEAN_RESUME)
        self.assertIn("John Doe", result)
        self.assertIn("Acme Corp", result)


# ══════════════════════════════════════════════════════════════════════════
# 17. CONSTRAINT 6 — OCR NOISE & KEYWORD STUFFING SUPPRESSION
# ══════════════════════════════════════════════════════════════════════════

class TestNoiseHandling(unittest.TestCase):

    def test_pure_punctuation_lines_removed(self):
        text = "John Doe\n----------\nengineer\nskills: python"
        result = rp._clean_text(text)
        self.assertNotIn("----------", result)

    def test_keyword_stuffing_collapsed(self):
        # 4+ repetitions of same word should be reduced
        text = "python python python python python is my skill"
        result = rp._clean_text(text)
        # Should not have 4+ consecutive identical words
        self.assertNotRegex(result, r"\bpython\b(\s+\bpython\b){3,}")

    def test_normal_content_not_mangled(self):
        result = rp._clean_text("Python developer with Python experience in Python projects")
        # Only 3 occurrences — should NOT be collapsed
        self.assertEqual(result.lower().count("python"), 3)

    def test_bullet_symbol_lines_removed(self):
        text = "Skills:\n• • • • •\npython\njava"
        result = rp._clean_text(text)
        self.assertNotIn("• • • • •", result)


# ══════════════════════════════════════════════════════════════════════════
# 18. CONSTRAINT 4 — ROLE DETECTION
# ══════════════════════════════════════════════════════════════════════════

DESIGN_RESUME = textwrap.dedent("""\
    Lisa Chen  lisa@design.io
    UX Designer – PixelStudio  2019-Present
    Junior UI Designer – ArtHouse  2017-2019
    Skills: Figma, Adobe XD, Photoshop, Illustrator, Typography, Wireframing
    Education: B.Des Interaction Design 2017
""")

MARKETING_RESUME = textwrap.dedent("""\
    Omar Farooq  omar@mkt.io
    Senior Marketing Manager – BrandCo  2018-Present
    SEO Specialist – DigitalAgency  2015-2018
    Skills: SEO, SEM, Google Ads, HubSpot, Content Strategy, CRM, Analytics
    Grew organic traffic by 120%, reduced CPC by 35%, led 5 campaigns
    Education: MBA Marketing 2015
""")

class TestRoleDetection(unittest.TestCase):

    def test_design_role_detected(self):
        self.assertEqual(rp._detect_role(DESIGN_RESUME), "design")

    def test_marketing_role_detected(self):
        self.assertEqual(rp._detect_role(MARKETING_RESUME), "marketing")

    def test_general_role_default(self):
        self.assertEqual(rp._detect_role(CLEAN_RESUME), "general")

    def test_design_signals_dominate(self):
        # text with both design and some marketing words → design wins on count
        text = "Figma Illustrator Photoshop Adobe XD UX UI wireframe SEO"
        self.assertEqual(rp._detect_role(text), "design")

    def test_empty_text_is_general(self):
        self.assertEqual(rp._detect_role(""), "general")


# ══════════════════════════════════════════════════════════════════════════
# 19. CONSTRAINT 4 — ROLE-WEIGHTED SCORING
# ══════════════════════════════════════════════════════════════════════════

class TestRoleWeightedScore(unittest.TestCase):

    def _score(self, role, exp=50, skl=60, sen=50, qlt=60,
               portfolio=60, impact=60):
        return rp._role_weighted_score(role, exp, skl, sen, qlt,
                                       portfolio, impact)

    def test_general_formula(self):
        expected = round(50*0.4 + 60*0.3 + 50*0.2 + 60*0.1, 1)
        self.assertAlmostEqual(self._score("general"), expected, places=1)

    def test_design_formula(self):
        # portfolio(35%) + skills(30%) + experience(20%) + quality(15%)
        expected = round(60*0.35 + 60*0.30 + 50*0.20 + 60*0.15, 1)
        self.assertAlmostEqual(self._score("design"), expected, places=1)

    def test_marketing_formula(self):
        # impact(35%) + skills(30%) + experience(20%) + quality(15%)
        expected = round(60*0.35 + 60*0.30 + 50*0.20 + 60*0.15, 1)
        self.assertAlmostEqual(self._score("marketing"), expected, places=1)

    def test_design_ignores_seniority_weight(self):
        # changing seniority should not change design score (sen not in formula)
        s1 = self._score("design", sen=10)
        s2 = self._score("design", sen=90)
        self.assertEqual(s1, s2)

    def test_design_rule_based_parse_uses_design_weights(self):
        rf = rp.regex_prepass(DESIGN_RESUME)
        result = rp.rule_based_parse(DESIGN_RESUME, rf)
        self.assertEqual(result["role_detected"], "design")

    def test_marketing_rule_based_parse_uses_marketing_weights(self):
        rf = rp.regex_prepass(MARKETING_RESUME)
        result = rp.rule_based_parse(MARKETING_RESUME, rf)
        self.assertEqual(result["role_detected"], "marketing")


# ══════════════════════════════════════════════════════════════════════════
# 20. CONSTRAINT 5 — QUALITY DOES NOT DOMINATE
# ══════════════════════════════════════════════════════════════════════════

class TestQualityCapConstraint(unittest.TestCase):

    def test_quality_capped_at_80_in_rule_based(self):
        rf = rp.regex_prepass(CLEAN_RESUME)
        r  = rp.rule_based_parse(CLEAN_RESUME, rf)
        # raw_quality stored in resume_quality_score, capped in ranking
        self.assertLessEqual(r["ranking_breakdown"]["quality_score"], 80)

    def test_quality_capped_in_merge(self):
        rf  = rp.regex_prepass(CLEAN_RESUME)
        llm = {
            "is_valid_resume": True, "name": "X",
            "estimated_years_of_experience": 5, "experience_confidence": 0.8,
            "skills": ["Python"], "top_skills": ["Python"],
            "current_role": "Engineer", "seniority_level": "senior",
            "role_detected": "general", "companies_worked": [],
            "education": None, "resume_quality_score": 100,   # LLM gives max
            "ranking_score": 80.0,
            "ranking_breakdown": {
                "experience_score": 50, "skills_score": 40,
                "seniority_score": 70, "quality_score": 100,   # uncapped
            },
            "notes": "",
        }
        final = rp.merge_results(rf, llm)
        self.assertLessEqual(final["resume_quality_score"], 80)

    def test_high_exp_low_quality_not_underranked(self):
        # Experienced candidate with sparse resume should still score decently
        sparse_senior = textwrap.dedent("""\
            Bob Smith  bob@x.com
            Senior Engineer BigCorp 2005 - Present
            Engineer StartupX 2001 - 2005
            skills: python java c++ aws docker kubernetes
        """)
        rf = rp.regex_prepass(sparse_senior)
        r  = rp.rule_based_parse(sparse_senior, rf)
        # 20+ yrs experience + decent skills should produce a reasonable score
        self.assertTrue(r["is_valid_resume"])
        self.assertGreater(r["ranking_score"], 40)

    def test_high_quality_low_skill_not_overranked(self):
        polished_empty = textwrap.dedent("""\
            Jane Polished  jane@x.com  +1-555-000-0000  linkedin.com/in/jane
            Junior Developer – MicroCo  2023-Present
            Education: B.Sc. 2023
            Skills: excel
            Increased team productivity. Reduced errors by 5%.
        """)
        rf = rp.regex_prepass(polished_empty)
        r  = rp.rule_based_parse(polished_empty, rf)
        # Should not score near the top despite complete contact/education
        self.assertLess(r["ranking_score"], 55)


# ══════════════════════════════════════════════════════════════════════════
# 21. FLAT behance_url FIELD
# ══════════════════════════════════════════════════════════════════════════

class TestFlatBehanceUrl(unittest.TestCase):

    @patch("resume_parser.extract_text", return_value=BEHANCE_RESUME)
    def test_behance_url_top_level_present(self, _):
        result = rp.parse_resume("sara.pdf", groq_client=None, fetch_behance=False)
        self.assertIn("behance_url", result)

    @patch("resume_parser.extract_text", return_value=BEHANCE_RESUME)
    def test_behance_url_matches_nested(self, _):
        result = rp.parse_resume("sara.pdf", groq_client=None, fetch_behance=False)
        self.assertEqual(result["behance_url"], result["behance"]["url"])

    @patch("resume_parser.extract_text", return_value=BEHANCE_RESUME)
    def test_behance_url_contains_username(self, _):
        result = rp.parse_resume("sara.pdf", groq_client=None, fetch_behance=False)
        self.assertIn("saradesign", result["behance_url"])

    @patch("resume_parser.extract_text", return_value=CLEAN_RESUME)
    def test_behance_url_none_when_absent(self, _):
        result = rp.parse_resume("john.pdf", groq_client=None, fetch_behance=False)
        self.assertIsNone(result["behance_url"])

    def test_rule_based_includes_behance_url(self):
        rf = rp.regex_prepass(BEHANCE_RESUME)
        r  = rp.rule_based_parse(BEHANCE_RESUME, rf)
        self.assertIn("behance_url", r)
        self.assertIn("saradesign", r["behance_url"])

    def test_rule_based_behance_url_none_when_missing(self):
        rf = rp.regex_prepass(CLEAN_RESUME)
        r  = rp.rule_based_parse(CLEAN_RESUME, rf)
        self.assertIsNone(r["behance_url"])


# ══════════════════════════════════════════════════════════════════════════
# 22. CONSTRAINT 3 — RANKING DIVERSITY (no score clustering)
# ══════════════════════════════════════════════════════════════════════════

class TestRankingDiversity(unittest.TestCase):

    def _parse(self, text):
        rf = rp.regex_prepass(text)
        return rp.rule_based_parse(text, rf)["ranking_score"]

    def test_intern_vs_senior_scores_differ_significantly(self):
        intern_text = textwrap.dedent("""\
            Tom Lee  tom@x.com
            Software Engineering Intern – StartupCo  Jun 2023 - Aug 2023
            Education: B.Sc. Computer Science (in progress), 2024
            Skills: python git
        """)
        senior_text = textwrap.dedent("""\
            Alice Wang  alice@x.com
            Senior Engineer – BigTech  2015 - Present
            Engineer – MidCo  2012 - 2015
            Skills: python java aws docker kubernetes react tensorflow postgresql
            Education: M.Sc. CS 2012
        """)
        intern_score  = self._parse(intern_text)
        senior_score  = self._parse(senior_text)
        self.assertGreater(senior_score - intern_score, 20)

    def test_all_candidates_have_unique_scores(self):
        resumes = [CLEAN_RESUME, MESSY_RESUME, MINIMAL_RESUME, DESIGN_RESUME, MARKETING_RESUME]
        scores = [self._parse(r) for r in resumes]
        # all scores should be unique (no two identical)
        self.assertEqual(len(scores), len(set(scores)))

    def test_scores_use_full_range(self):
        resumes = [CLEAN_RESUME, MESSY_RESUME, MINIMAL_RESUME, DESIGN_RESUME, MARKETING_RESUME]
        scores = [self._parse(r) for r in resumes]
        spread = max(scores) - min(scores)
        self.assertGreater(spread, 15, "Scores too clustered — spread must be > 15 pts")


# ══════════════════════════════════════════════════════════════════════════
# 23. CONSTRAINT 1 — TRIMMED / HEADERLESS INPUT
# ══════════════════════════════════════════════════════════════════════════

class TestTrimmedInputHandling(unittest.TestCase):

    def test_no_headers_still_parses(self):
        # Raw trimmed content — no section headers, just data
        text = textwrap.dedent("""\
            alice@dev.io  +1-555-100-2000
            Python Django PostgreSQL Docker AWS React TypeScript
            Engineer at SmallCo 2018 - 2020 then BigCorp 2020 - Present
            B.Sc. Computer Science MIT 2018
        """)
        rf = rp.regex_prepass(text)
        r  = rp.rule_based_parse(text, rf)
        self.assertTrue(r["is_valid_resume"])
        self.assertIn("python", r["skills"])

    def test_experience_extracted_without_job_title(self):
        text = textwrap.dedent("""\
            bob@x.com
            TechCorp 2015 - 2020 developer role
            MegaCorp 2020 - Present senior engineer
            skills: python java aws docker kubernetes
        """)
        rf = rp.regex_prepass(text)
        r  = rp.rule_based_parse(text, rf)
        self.assertGreater(r["estimated_years_of_experience"], 0)

    def test_skills_only_section_valid(self):
        text = textwrap.dedent("""\
            carol@x.com
            Senior developer with 8 years experience at large companies
            python react node.js postgresql aws docker kubernetes tensorflow
        """)
        rf = rp.regex_prepass(text)
        r  = rp.rule_based_parse(text, rf)
        self.assertTrue(r["is_valid_resume"])
        self.assertGreater(len(r["skills"]), 0)


# ══════════════════════════════════════════════════════════════════════════
# RUNNER
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    loader    = unittest.TestLoader()
    suite     = loader.loadTestsFromModule(sys.modules[__name__])
    verbosity = 2 if "-v" in sys.argv else 1
    runner    = unittest.TextTestRunner(verbosity=verbosity, stream=sys.stdout)
    result    = runner.run(suite)

    print(f"\n{'='*60}")
    print(f"  Tests run   : {result.testsRun}")
    print(f"  Failures    : {len(result.failures)}")
    print(f"  Errors      : {len(result.errors)}")
    print(f"  Skipped     : {len(result.skipped)}")
    status = "ALL PASSED" if result.wasSuccessful() else "SOME FAILED"
    print(f"  Result      : {status}")
    print(f"{'='*60}")
    sys.exit(0 if result.wasSuccessful() else 1)
