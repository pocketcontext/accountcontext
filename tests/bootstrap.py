"""The one-use initializer cannot target a sibling or accept caller settings."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('bootstrap', Path(__file__).resolve().parents[1] / 'deploy/bootstrap-accountcontext.py')
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        settings = {'ACCOUNTCONTEXT_' + k: 'synthetic' for k in ('SUPERUSER_EMAIL', 'SUPERUSER_PASSWORD', 'GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 'GOOGLE_WORKSPACE_DOMAIN', 'TRUSTED_PROXY_HEADER')}
        settings.update({'LITESTREAM_' + k: 'synthetic' for k in ('BUCKET', 'PATH', 'REGION', 'ENDPOINT', 'ACCESS_KEY_ID', 'SECRET_ACCESS_KEY')})
        settings.update(LITESTREAM_BUCKET='accountcontext-backup', LITESTREAM_PATH='once-pocketcontext/accountcontext')
        self.payload = {'image': 'ghcr.io/pocketcontext/accountcontext@sha256:' + 'a' * 64, 'settings': settings}
        self.credential = {'username': 'synthetic', 'token': 'x' * 40}

    def test_valid_pinned_target(self):
        self.assertEqual(bootstrap.validate(self.payload, self.credential), self.payload['settings'])

    def test_no_sibling_image_or_backup(self):
        with self.assertRaises(ValueError):
            bootstrap.validate(dict(self.payload, image=self.payload['image'].replace('accountcontext', 'raisecontext')), self.credential)
        self.payload['settings']['LITESTREAM_BUCKET'] = 'sibling'
        with self.assertRaises(ValueError):
            bootstrap.validate(self.payload, self.credential)

    def test_no_arbitrary_runtime_environment(self):
        self.payload['settings']['LITESTREAM_DISABLED'] = 'true'
        with self.assertRaises(ValueError):
            bootstrap.validate(self.payload, self.credential)

    def test_no_arbitrary_credential_payload(self):
        for credential in ({'username': 'name', 'token': 'x' * 40, 'settings': {}}, {'username': 'x\n', 'token': 'x' * 40}, {'username': 'name', 'token': 'short'}):
            with self.assertRaises(ValueError):
                bootstrap.validate(self.payload, credential)


if __name__ == '__main__':
    unittest.main()
