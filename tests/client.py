#!/usr/bin/env python3
"""Safety and failure behavior for portable imports and document export."""
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec=importlib.util.spec_from_file_location('ac',Path(__file__).resolve().parents[1]/'skills/accountcontext/scripts/ac.py')
ac=importlib.util.module_from_spec(spec);spec.loader.exec_module(ac)

class ClientTests(unittest.TestCase):
    def test_truncation_fails(self):
        with patch.object(ac,'must',return_value={'columns':['id'],'rows':[['a'*15]],'truncated':True}):
            with self.assertRaises(ac.Fail): ac.sql_rows({},'SELECT id FROM bills')

    def test_pagination_checks_order(self):
        with patch.object(ac,'sql_rows',return_value=[{'id':'a'*15}]):
            with self.assertRaises(ac.Fail): ac.all_rows({},'bills')
        with self.assertRaises(ac.Fail): ac.all_rows({},'bills;DELETE FROM bills')

    def test_download_checksum_and_filename(self):
        row={'id':'a'*15,'original':'receipt.pdf','sha256':hashlib.sha256(b'PDF').hexdigest()}
        with patch.object(ac,'must',return_value={'token':'secret'}),patch.object(ac,'binary_request',return_value=b'PDF'):
            self.assertEqual(ac.download_bytes({},row),b'PDF')
            with self.assertRaises(ac.Fail): ac.download_bytes({},dict(row,sha256='0'*64))
            with self.assertRaises(ac.Fail): ac.download_bytes({},dict(row,original='../receipt.pdf'))

    def test_atomic_csv_and_duplicate_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'input.csv'
            out=io.StringIO();writer=csv.writer(out);writer.writerow(['collection','json']);writer.writerow(['parties',json.dumps({'name':'Vendor'})]);source.write_text(out.getvalue())
            with patch.object(ac,'must',return_value=[]) as send:
                first=ac.import_csv({},source);second=ac.import_csv({},source)
                self.assertEqual(first['import_id'],second['import_id'])
                body=send.call_args.args[3]
                self.assertEqual(len(body['requests']),2)
                self.assertEqual(body['requests'][0]['body']['sha256'],hashlib.sha256(source.read_bytes()).hexdigest())
            source.write_text('collection,json\nusers,"{}"\n')
            with patch.object(ac,'must') as send:
                with self.assertRaises(ac.Fail):ac.import_csv({},source)
                send.assert_not_called()

    def test_private_write_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'out';ac.private_write(file,b'first')
            self.assertEqual(file.stat().st_mode&0o777,0o600)
            with self.assertRaises(FileExistsError):ac.private_write(file,b'second')
            self.assertEqual(file.read_bytes(),b'first')

    def test_export_changed_data_never_publishes(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'export.zip'
            counts={}
            def rows(cfg,table):
                counts[table]=counts.get(table,0)+1
                return [{'id':'a'*15,'name':str(counts[table])}] if table=='parties' else []
            with patch.object(ac,'must',return_value={'id':'b'*15,'revision':1}),patch.object(ac,'all_rows',side_effect=rows):
                with self.assertRaises(ac.Fail):ac.export_archive({'url':'https://accounts.example.com'},output)
            self.assertFalse(output.exists())

    def test_export_requires_permission_and_safe_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'export.zip'
            with patch.object(ac,'must',side_effect=ac.Fail(1,'forbidden')),patch.object(ac,'all_rows') as read:
                with self.assertRaises(ac.Fail):ac.export_archive({},output)
                read.assert_not_called()
            content=b'original'
            row={'id':'a'*15,'original':'../../../private.pdf','sha256':hashlib.sha256(content).hexdigest()}
            def rows(cfg,table): return [row] if table=='documents' else []
            with patch.object(ac,'must',return_value={'id':'b'*15,'revision':1}),patch.object(ac,'all_rows',side_effect=rows),patch.object(ac,'download_bytes',return_value=content):
                ac.export_archive({'url':'https://accounts.example.com'},output)
            with zipfile.ZipFile(output) as archive:
                manifest=json.loads(archive.read('manifest.json'))
                for entry in manifest['files']:
                    self.assertNotIn('..',Path(entry['path']).parts)
                    self.assertEqual(hashlib.sha256(archive.read(entry['path'])).hexdigest(),entry['sha256'])

    def test_formula_escaping(self):
        rows=list(csv.DictReader(io.StringIO(ac.csv_bytes([{'name':'=HYPERLINK("evil")','amount':-1}]).decode())))
        self.assertTrue(rows[0]['name'].startswith("'="));self.assertEqual(rows[0]['amount'],"'-1")

if __name__=='__main__':unittest.main()
