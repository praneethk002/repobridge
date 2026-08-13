"""Unit tests for .claude/skills/repobridge/scout.py.

Stdlib only (unittest + unittest.mock) — no network calls, no pip installs.
Run from the repo root:

    python3 -m unittest discover -s tests -v

These tests exercise the actual rule-based logic scout.py makes claims
about: license filtering (permissive allowed, copyleft blocked by default),
the staleness cutoff, the metadata scoring formula, awesome-list link
extraction, GitHub auth resolution, and API error handling. Nothing here
is mocked into passing regardless of the code — each test asserts a
specific, checkable outcome against the real functions.
"""

import sys
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".claude" / "skills" / "repobridge"))
import scout  # noqa: E402


def iso_months_ago(months):
    dt = datetime.now(timezone.utc) - timedelta(days=months * 30.44)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def make_repo(license_spdx="MIT", months_old=1, stars=10, full_name="o/r",
              description="", topics=None):
    return {
        "id": 1, "full_name": full_name, "url": "https://github.com/" + full_name,
        "description": description, "stars": stars, "license_spdx": license_spdx,
        "pushed_at": iso_months_ago(months_old), "language": "Python",
        "topics": topics or [], "default_branch": "main",
    }


class NormalizeTests(unittest.TestCase):
    def test_extracts_core_fields_from_a_github_api_item(self):
        item = {
            "id": 1, "full_name": "owner/repo", "html_url": "https://github.com/owner/repo",
            "description": "A thing", "stargazers_count": 42,
            "license": {"spdx_id": "MIT"}, "pushed_at": iso_months_ago(1),
            "language": "Python", "topics": ["cli"], "default_branch": "main",
        }
        r = scout.normalize(item)
        self.assertEqual(r["full_name"], "owner/repo")
        self.assertEqual(r["license_spdx"], "MIT")
        self.assertEqual(r["stars"], 42)
        self.assertEqual(r["default_branch"], "main")

    def test_handles_missing_license_and_description(self):
        item = {
            "id": 2, "full_name": "owner/repo2", "html_url": "u",
            "description": None, "stargazers_count": 0, "license": None,
            "pushed_at": iso_months_ago(1), "language": None, "topics": [],
        }
        r = scout.normalize(item)
        self.assertEqual(r["description"], "")
        self.assertIsNone(r["license_spdx"])


class HardFilterTests(unittest.TestCase):
    """These tests are the direct check on the licensing and staleness
    claims made in docs/plan.md and the top-level README."""

    def test_repo_with_no_license_is_dropped(self):
        repos = [make_repo(license_spdx=None)]
        self.assertEqual(scout.apply_hard_filters(repos, False, 12), [])

    def test_repo_with_noassertion_license_is_dropped(self):
        repos = [make_repo(license_spdx="NOASSERTION")]
        self.assertEqual(scout.apply_hard_filters(repos, False, 12), [])

    def test_permissive_license_passes(self):
        for spdx in ("MIT", "Apache-2.0", "BSD-3-Clause", "ISC"):
            with self.subTest(spdx=spdx):
                repos = [make_repo(license_spdx=spdx)]
                self.assertEqual(len(scout.apply_hard_filters(repos, False, 12)), 1)

    def test_copyleft_license_blocked_by_default(self):
        for spdx in ("GPL-3.0", "GPL-2.0", "AGPL-3.0", "LGPL-3.0"):
            with self.subTest(spdx=spdx):
                repos = [make_repo(license_spdx=spdx)]
                self.assertEqual(scout.apply_hard_filters(repos, False, 12), [])

    def test_copyleft_license_kept_with_explicit_override(self):
        repos = [make_repo(license_spdx="GPL-3.0")]
        self.assertEqual(len(scout.apply_hard_filters(repos, True, 12)), 1)

    def test_repo_older_than_stale_threshold_is_dropped(self):
        repos = [make_repo(months_old=13)]
        self.assertEqual(scout.apply_hard_filters(repos, False, 12), [])

    def test_repo_within_stale_threshold_is_kept(self):
        repos = [make_repo(months_old=11)]
        self.assertEqual(len(scout.apply_hard_filters(repos, False, 12)), 1)

    def test_custom_stale_threshold_is_respected(self):
        repos = [make_repo(months_old=7)]
        self.assertEqual(scout.apply_hard_filters(repos, False, 6), [])
        self.assertEqual(len(scout.apply_hard_filters(repos, False, 12)), 1)


class ScoringTests(unittest.TestCase):
    """Checks the metadata_score formula: recency (0-30) + stars (0-40,
    capped at 5000) + keyword overlap (0-30)."""

    def test_fresh_high_star_matching_repo_scores_near_max(self):
        repo = make_repo(months_old=0, stars=5000, description="habit tracker with streaks",
                          topics=["streaks"])
        scored = scout.score_metadata(repo, ["streaks"])
        self.assertGreater(scored["metadata_score"], 95)

    def test_stale_low_star_nonmatching_repo_scores_low(self):
        repo = make_repo(months_old=11.9, stars=0, description="", topics=[])
        scored = scout.score_metadata(repo, [])
        self.assertLess(scored["metadata_score"], 5)

    def test_stars_component_is_capped_at_5000(self):
        cheap = scout.score_metadata(make_repo(months_old=0, stars=5000), [])
        expensive = scout.score_metadata(make_repo(months_old=0, stars=50000), [])
        self.assertEqual(cheap["score_breakdown"]["stars"], expensive["score_breakdown"]["stars"])

    def test_keyword_overlap_counts_fractional_matches(self):
        repo = make_repo(full_name="o/habit-app", description="streak tracking app",
                          topics=["social"])
        overlap = scout.keyword_overlap(repo, ["streak tracking", "social", "reminders"])
        self.assertAlmostEqual(overlap, 2 / 3)

    def test_no_requirements_gives_zero_overlap(self):
        repo = make_repo(description="anything")
        self.assertEqual(scout.keyword_overlap(repo, []), 0.0)

    def test_score_breakdown_sums_to_metadata_score(self):
        repo = make_repo(months_old=3, stars=800, description="streaks", topics=[])
        scored = scout.score_metadata(repo, ["streaks"])
        breakdown_sum = sum(scored["score_breakdown"].values())
        self.assertAlmostEqual(scored["metadata_score"], breakdown_sum, places=1)


class LinkExtractionTests(unittest.TestCase):
    """The awesome-list bonus-candidate mechanism: mining repo links out of
    a curated list's README instead of adding a new search API."""

    def test_extracts_valid_owner_repo_links(self):
        readme = "Check out https://github.com/foo/bar and github.com/baz/qux!"
        links = scout.extract_repo_links(readme, "self/self")
        self.assertIn("foo/bar", links)
        self.assertIn("baz/qux", links)

    def test_excludes_non_repo_site_sections(self):
        readme = "See github.com/topics/awesome or github.com/sponsors/someone"
        links = scout.extract_repo_links(readme, "self/self")
        self.assertEqual(links, [])

    def test_excludes_self_reference(self):
        readme = "This is github.com/self/self, our own repo."
        links = scout.extract_repo_links(readme, "self/self")
        self.assertEqual(links, [])

    def test_dedupes_repeated_links(self):
        readme = "github.com/foo/bar github.com/foo/bar github.com/foo/bar"
        links = scout.extract_repo_links(readme, "self/self")
        self.assertEqual(links, ["foo/bar"])

    def test_caps_at_max_extracted_links(self):
        readme = " ".join(f"github.com/org/repo{i}" for i in range(30))
        links = scout.extract_repo_links(readme, "self/self")
        self.assertEqual(len(links), scout.MAX_EXTRACTED_LINKS)


class AwesomeListDetectionTests(unittest.TestCase):
    def test_detects_by_name(self):
        repos = [make_repo(full_name="sindresorhus/awesome")]
        self.assertEqual(len(scout.find_awesome_lists(repos)), 1)

    def test_detects_by_topic(self):
        repos = [make_repo(full_name="someone/list", topics=["awesome-list"])]
        self.assertEqual(len(scout.find_awesome_lists(repos)), 1)

    def test_ignores_unrelated_repos(self):
        repos = [make_repo(full_name="someone/habit-tracker", topics=["habits"])]
        self.assertEqual(scout.find_awesome_lists(repos), [])

    def test_caps_at_max_awesome_lists(self):
        repos = [make_repo(full_name=f"o/awesome-{i}") for i in range(5)]
        self.assertEqual(len(scout.find_awesome_lists(repos)), scout.MAX_AWESOME_LISTS)


class AuthTests(unittest.TestCase):
    def test_uses_github_token_env_var_when_present(self):
        with patch.dict("os.environ", {"GITHUB_TOKEN": "env-token"}):
            self.assertEqual(scout.get_token(), "env-token")

    @patch("scout.subprocess.run")
    def test_falls_back_to_gh_cli_when_no_env_var(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="gh-token\n")
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(scout.get_token(), "gh-token")

    @patch("scout.subprocess.run")
    def test_exits_when_gh_cli_not_authenticated(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(SystemExit):
                scout.get_token()

    def test_exits_when_gh_cli_not_installed(self):
        with patch("scout.subprocess.run", side_effect=FileNotFoundError):
            with patch.dict("os.environ", {}, clear=True):
                with self.assertRaises(SystemExit):
                    scout.get_token()


class ApiRequestTests(unittest.TestCase):
    """Confirms fail-loud behavior on rate limits and configurable
    soft-fail behavior for expected 404s, entirely offline via mocks."""

    @patch("scout.urllib.request.urlopen")
    def test_rate_limit_error_exits_nonzero(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "url", 403, "Forbidden", {}, BytesIO(b'{"message": "API rate limit exceeded"}')
        )
        with self.assertRaises(SystemExit):
            scout.api_request("/search/repositories", "token")

    @patch("scout.urllib.request.urlopen")
    def test_other_http_errors_also_exit_nonzero(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "url", 500, "Server Error", {}, BytesIO(b"{}")
        )
        with self.assertRaises(SystemExit):
            scout.api_request("/repos/foo/bar", "token")

    @patch("scout.urllib.request.urlopen")
    def test_soft_fail_status_returns_none_instead_of_exiting(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "url", 404, "Not Found", {}, BytesIO(b"{}")
        )
        result = scout.api_request("/repos/foo/bar", "token", soft_fail_statuses=(404,))
        self.assertIsNone(result)

    @patch("scout.urllib.request.urlopen")
    def test_successful_response_is_parsed_as_json(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"ok": true}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp
        result = scout.api_request("/repos/foo/bar", "token")
        self.assertEqual(result, {"ok": True})


if __name__ == "__main__":
    unittest.main()
