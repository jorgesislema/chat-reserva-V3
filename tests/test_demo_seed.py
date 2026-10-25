"""Validación de la carga ficticia con unittest y SQLite, sin servicios externos."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import seed_demo_crm
from crm.calendar import sync
from crm.store import connect, initialize


class DemoSeedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'demo.db'
        initialize(self.path)

    def seed(self):
        with patch.object(seed_demo_crm, 'ROOT', self.root), patch.dict(
                'os.environ', {'CRM_DATABASE': str(self.path), 'CRM_TIMEZONE': 'America/Guayaquil'}), redirect_stdout(StringIO()):
            seed_demo_crm.seed()

    def test_repeated_load_preserves_counts_and_has_no_overlap(self):
        self.seed()
        with connect(self.path) as db:
            count = db.execute('SELECT COUNT(*) FROM crm_appointments').fetchone()[0]
        self.seed()
        with connect(self.path) as db:
            self.assertEqual(count, db.execute('SELECT COUNT(*) FROM crm_appointments').fetchone()[0])
            self.assertEqual(60, db.execute('SELECT COUNT(*) FROM crm_leads').fetchone()[0])
            self.assertEqual(3, db.execute('SELECT COUNT(*) FROM crm_professionals').fetchone()[0])
            self.assertEqual(0, db.execute('SELECT COUNT(*) FROM crm_users').fetchone()[0])
            self.assertEqual([], db.execute('PRAGMA foreign_key_check').fetchall())
            overlaps = db.execute('''SELECT COUNT(*) FROM crm_appointments a JOIN crm_appointments b
                ON a.professional_id=b.professional_id AND a.id<b.id
                AND a.start<b.end AND a.end>b.start''').fetchone()[0]
            self.assertEqual(0, overlaps)
        self.assertEqual(2, len(list((self.root / 'backups').glob('*.db'))))

    def test_edited_demo_cannot_be_sent_to_google(self):
        self.seed()
        with connect(self.path) as db:
            db.execute("INSERT INTO crm_accounts(id,email,credential_env,name) VALUES (1,'test@example.invalid','TEST_CREDS','Test')")
            db.execute("UPDATE crm_professionals SET account_id=1,calendar_id='calendar-'||id")
            db.execute("UPDATE crm_appointments SET sync_status='pending'")
        service = MagicMock()
        service.events().list().execute.return_value = {'items': []}
        sync(self.path, service_factory=lambda _: service)
        service.events().patch.assert_not_called()
        service.events().insert.assert_not_called()
        service.events().delete.assert_not_called()


if __name__ == '__main__':
    unittest.main()
