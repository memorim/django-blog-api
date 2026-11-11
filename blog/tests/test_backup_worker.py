import json
import subprocess
from unittest import TestCase
from unittest.mock import Mock

from scripts.backup_worker import BackupWorker


class BackupWorkerTests(TestCase):
    def test_restore_must_match_the_archived_checksum(self):
        runner = Mock(side_effect=[
            subprocess.CompletedProcess([], 0, json.dumps({"snapshot": 3, "sha256": "checked"})),
            subprocess.CompletedProcess([], 0, json.dumps({"restored": True, "sha256": "checked"})),
        ])
        worker = BackupWorker(runner)
        code, summary = worker.run(restore=True)
        self.assertEqual(code, 200)
        self.assertTrue(summary["restored"])
        self.assertEqual(runner.call_args.args[0][-2:], ["--snapshot", "3"])

    def test_private_subprocess_errors_are_not_returned(self):
        runner = Mock(side_effect=subprocess.CalledProcessError(1, [], stderr="private-content"))
        worker = BackupWorker(runner)
        self.assertEqual(worker.run(), (503, {"status": "failed"}))
        self.assertIsNone(worker.last)

    def test_only_one_backup_can_run_at_a_time(self):
        runner = Mock()
        worker = BackupWorker(runner)
        with worker.lock:
            self.assertEqual(worker.run(), (409, {"status": "running"}))
        runner.assert_not_called()
