import os
import unittest

from tools import eventdata, hydrate, scan
from tools.tests import fixtures


class TestHydrate(fixtures.ArchiveFixture, unittest.TestCase):
    def ids_for(self, needle):
        # Exclude catch-all mirrors: collect_events() returns one record per
        # (top, year, event, catchall) group, so a non-catchall event that is
        # also byte-mirrored into a catch-all folder (as the fixture's
        # "1023 Rendr Dinner" deliberately is, to exercise dupes.py) produces
        # two distinct ids with the same title. Every production caller
        # (manifests.py) filters these out before exposing ids to a person --
        # the manifest never lists a catch-all row to tick -- so real
        # event_ids passed to hydrate.run() never include one. Matching that
        # convention here, rather than the brief's original unfiltered
        # version, which picked up both ids for "Rendr Dinner" and inflated
        # events/files/already by 2x.
        events = eventdata.collect_events(list(scan.walk(self.archive_root)))
        return [e["id"] for e in events if needle in e["title"] and not e["catchall"]]

    def test_local_fixture_files_report_as_hydrated(self):
        path = next(r["path"] for r in scan.walk(self.archive_root))
        self.assertTrue(hydrate.is_hydrated(path))

    def test_pull_reads_a_file_successfully(self):
        path = next(r["path"] for r in scan.walk(self.archive_root))
        self.assertTrue(hydrate.pull(path))

    def test_pull_reports_failure_for_a_missing_file(self):
        self.assertFalse(hydrate.pull(os.path.join(self.archive_root, "nope.jpg")))

    def test_run_touches_only_the_requested_events(self):
        target = self.ids_for("Rendr Dinner")
        seen = []
        result = hydrate.run(self.archive_root, target,
                             progress=lambda row: seen.append(row["rel"]))
        self.assertEqual(result["events"], 1)
        self.assertEqual(result["files"], 3)   # fixture plants 3 photos
        self.assertTrue(all("Rendr Dinner" in rel for rel in seen))

    def test_run_skips_files_already_present(self):
        target = self.ids_for("Rendr Dinner")
        result = hydrate.run(self.archive_root, target)
        self.assertEqual(result["already"], 3)
        self.assertEqual(result["pulled"], 0)

    def test_run_ignores_unknown_ids(self):
        result = hydrate.run(self.archive_root, ["no-such-event-id"])
        self.assertEqual(result["events"], 0)
        self.assertEqual(result["files"], 0)

    def test_run_never_writes_to_the_archive(self):
        before = sorted(
            (os.path.relpath(os.path.join(dp, f), self.archive_root),
             os.path.getsize(os.path.join(dp, f)))
            for dp, dn, fs in os.walk(self.archive_root) for f in fs
        )
        hydrate.run(self.archive_root, self.ids_for("Rendr Dinner"))
        after = sorted(
            (os.path.relpath(os.path.join(dp, f), self.archive_root),
             os.path.getsize(os.path.join(dp, f)))
            for dp, dn, fs in os.walk(self.archive_root) for f in fs
        )
        self.assertEqual(before, after)


class TestManifestParsing(unittest.TestCase):
    def setUp(self):
        self.tmp = fixtures.make_tempdir()
        self.path = os.path.join(self.tmp, "events-manifest.md")
        with open(self.path, "w") as fh:
            fh.write(
                "| pick | date | event | photos | physician | partners | id |\n"
                "|---|---|---|---|---|---|---|\n"
                "| [x] | 2026-06-09 | Diabetes | 11 |  |  | `2026-06-09-diabetes` |\n"
                "| [ ] | 2026-03-01 | Parade | 4 |  |  | `2026-03-01-parade` |\n"
                "| [X] | 2025-05-08 | Opening | 27 |  |  | `2025-05-08-opening` |\n"
            )

    def tearDown(self):
        fixtures.cleanup(self.tmp)

    def test_reads_only_ticked_rows_case_insensitively(self):
        self.assertEqual(
            hydrate.ids_from_manifest(self.path),
            ["2026-06-09-diabetes", "2025-05-08-opening"],
        )
