#!/usr/bin/env python3
"""Synthetic read-after-write checks for reused filtered SQL snapshots.

The pinned server retains each requester's private snapshot while the source
database is unchanged. These checks prove reuse with X-Context-Snapshot-At
(unchanged on a cache hit), then require claim, document and finance-membership
writes to be visible on the very next read, with no stale company-wide rows
after revocation and no leakage between claimants, finance members and
unrelated users.
"""
import argparse
import concurrent.futures
import hashlib
import json
import time
import urllib.error
import urllib.request
from integration import server

PASSWORD = 'SyntheticUserPassword123!'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--binary', required=True)
    args = ap.parse_args()
    with server(args.binary) as req:
        p = lambda t: '/api/collections/' + t + '/records'
        admin = req('POST', '/api/collections/_superusers/auth-with-password',
                    {'identity': 'admin@example.com', 'password': 'SyntheticAdminPassword123!'})['token']

        def account(email):
            user = req('POST', p('users'), {'email': email, 'name': email, 'password': PASSWORD, 'passwordConfirm': PASSWORD}, admin)
            return user, req('POST', '/api/collections/users/auth-with-password', {'identity': email, 'password': PASSWORD})['token']

        timings = []

        def sql(query, token, expected=200):
            request = urllib.request.Request(req.base_url + '/api/context/query', data=json.dumps({'sql': query}).encode(),
                                             headers={'Content-Type': 'application/json', 'Authorization': token}, method='POST')
            started = time.monotonic()
            try:
                with urllib.request.urlopen(request, timeout=25) as response:
                    status, raw, headers = response.status, response.read(), response.headers
            except urllib.error.HTTPError as error:
                status, raw, headers = error.code, error.read(), error.headers
            elapsed = time.monotonic() - started
            assert status in (expected if isinstance(expected, tuple) else (expected,)), (query, status, raw.decode())
            if status != 200:
                return None, None
            assert headers['X-Context-Scope'] == 'authorized-snapshot'
            result = json.loads(raw)
            assert not result['truncated']
            timings.append((headers['X-Context-Snapshot-At'], elapsed))
            return [dict(zip(result['columns'], row)) for row in result['rows']], headers['X-Context-Snapshot-At']

        def warm(query, token):
            """Read twice: an unchanged capture time proves the second read reused the snapshot."""
            rows, first = sql(query, token)
            again, second = sql(query, token)
            assert rows == again and first == second, 'expected a reused snapshot for an unchanged source'
            return rows, first

        def fresh(query, token, before):
            """The first read after a commit must come from a new capture."""
            rows, at = sql(query, token)
            assert at != before, 'a committed write must invalidate the reused snapshot'
            return rows

        def ids(rows):
            return sorted(r['id'] for r in rows)

        def upload(owner, token, title):
            boundary = 'accountcontext-freshness-boundary'
            content = ('Synthetic original ' + title + '\n').encode()
            body = (f'--{boundary}\r\nContent-Disposition: form-data; name="title"\r\n\r\n{title}\r\n'
                    f'--{boundary}\r\nContent-Disposition: form-data; name="owner"\r\n\r\n{owner}\r\n'
                    f'--{boundary}\r\nContent-Disposition: form-data; name="original"; filename="receipt.txt"\r\n'
                    'Content-Type: text/plain\r\n\r\n').encode() + content + f'\r\n--{boundary}--\r\n'.encode()
            request = urllib.request.Request(req.base_url + p('documents'), body, {'Content-Type': 'multipart/form-data; boundary=' + boundary,
                                                                                 'Authorization': token}, method='POST')
            with urllib.request.urlopen(request) as response:
                doc = json.load(response)
            assert doc['sha256'] == hashlib.sha256(content).hexdigest()
            return doc

        fin, ft = account('finance@example.com')
        claimant, ct = account('claimant@example.com')
        other, ot = account('other@example.com')
        role = req('POST', p('finance_members'), {'account': fin['id'], 'can_approve': True}, admin)
        schema = req('GET', '/api/context/schema', token=ct)
        assert schema['permissionModel'] == 'filtered-snapshot' and 'snapshot' not in schema
        assert schema['snapshotLimits']['maxConcurrentPerRequester'] == 0, 'per-requester admission must stay disabled'

        claims = 'SELECT id,owner,status,revision FROM claims ORDER BY id'
        documents = 'SELECT id,owner FROM documents ORDER BY id'
        parties = 'SELECT id FROM parties ORDER BY id'
        directory = 'SELECT id FROM user_directory ORDER BY id'
        audit = 'SELECT id,record,owner FROM audit_log ORDER BY created,id'
        party = req('POST', p('parties'), {'name': 'Synthetic supplier'}, ft)

        # An own document upload is visible at once to its owner, never to an unrelated user.
        _, claimant_at = warm(documents, ct)
        _, other_at = warm(documents, ot)
        doc = upload(claimant['id'], ct, 'Synthetic taxi receipt')
        assert ids(fresh(documents, ct, claimant_at)) == [doc['id']]
        assert fresh(documents, ot, other_at) == []

        # Own-claim creation is visible at once to the claimant and finance, never to an unrelated user.
        _, fin_at = warm(claims, ft)
        _, claimant_at = warm(claims, ct)
        _, other_at = warm(claims, ot)
        _, audit_at = warm(audit, ct)
        claim = req('POST', p('claims'), {'owner': claimant['id'], 'document': doc['id'], 'title': 'Synthetic taxi',
                                          'payer': 'Synthetic claimant', 'business_purpose': 'Synthetic travel', 'currency': 'USD', 'currency_exponent': 2,
                                          'amount_minor': 2500, 'status': 'draft'}, ct)
        assert ids(fresh(claims, ct, claimant_at)) == [claim['id']]
        assert ids(fresh(claims, ft, fin_at)) == [claim['id']]
        assert fresh(claims, ot, other_at) == []
        own_audit = fresh(audit, ct, audit_at)
        assert any(r['record'] == claim['id'] for r in own_audit) and all(r['owner'] == claimant['id'] for r in own_audit)
        assert sql(audit, ot)[0] == []

        # A status transition is visible on the next read.
        _, claimant_at = warm(claims, ct)
        _, fin_at = warm(claims, ft)
        claim = req('PATCH', p('claims') + '/' + claim['id'], {'expected_revision': claim['revision'], 'status': 'submitted'}, ct)
        mine = fresh(claims, ct, claimant_at)
        assert mine[0]['status'] == 'submitted' and mine[0]['revision'] == claim['revision']
        assert fresh(claims, ft, fin_at)[0]['revision'] == claim['revision']

        # A finance grant takes effect on the grantee's next read; their cached own-only snapshot does not survive.
        _, other_at = warm(parties, ot)
        assert warm(directory, ot)[0] == [{'id': other['id']}]
        _, claimant_at = warm(parties, ct)
        grant = req('POST', p('finance_members'), {'account': other['id'], 'can_approve': False}, admin)
        assert ids(fresh(parties, ot, other_at)) == [party['id']]
        assert ids(sql(claims, ot)[0]) == [claim['id']] and ids(sql(documents, ot)[0]) == [doc['id']]
        assert len(sql(directory, ot)[0]) == 3
        assert fresh(parties, ct, claimant_at) == [], 'a grant to one account changes nothing for another'
        assert sql(directory, ct)[0] == [{'id': claimant['id']}]

        # Approval authority is independent: a finance reader without can_approve cannot approve until granted.
        req('PATCH', p('claims') + '/' + claim['id'], {'expected_revision': claim['revision'], 'status': 'approved'}, ot, 403)
        _, other_at = warm(claims, ot)
        grant = req('PATCH', p('finance_members') + '/' + grant['id'], {'can_approve': True}, admin)
        assert ids(fresh(claims, ot, other_at)) == [claim['id']]
        claim = req('PATCH', p('claims') + '/' + claim['id'], {'expected_revision': claim['revision'], 'status': 'approved'}, ot)
        _, claimant_at = warm(claims, ct)

        # Revocation removes company-wide rows from the very next read; only the account's own rows remain.
        _, other_at = warm(parties, ot)
        req('DELETE', p('finance_members') + '/' + grant['id'], token=admin, expected=204)
        assert fresh(parties, ot, other_at) == []
        assert sql(claims, ot)[0] == [] and sql(documents, ot)[0] == []
        assert sql(directory, ot)[0] == [{'id': other['id']}]
        assert all(r['owner'] == other['id'] for r in sql(audit, ot)[0])
        assert fresh(claims, ct, claimant_at)[0]['status'] == 'approved'

        # Revoking the original finance member also applies immediately.
        _, fin_at = warm(parties, ft)
        req('DELETE', p('finance_members') + '/' + role['id'], token=admin, expected=204)
        assert fresh(parties, ft, fin_at) == [] and sql(claims, ft)[0] == []

        # Concurrent reads from several tabs of one account are admitted (no per-requester 429).
        with concurrent.futures.ThreadPoolExecutor(8) as pool:
            results = list(pool.map(lambda _: sql(claims, ct)[0], range(8)))
        assert all(ids(result) == [claim['id']] for result in results)

        # Disabling an account is enforced before any cached snapshot can be served.
        warm(claims, ct)
        req('PATCH', p('users') + '/' + claimant['id'], {'disabled': True}, admin)
        sql(claims, ct, expected=(401, 403))

        seen, cold, hits = set(), [], []
        for captured, elapsed in timings:
            (hits if captured in seen else cold).append(elapsed)
            seen.add(captured)
        print(f'Snapshot reads: {len(cold)} cold median {sorted(cold)[len(cold) // 2] * 1000:.1f} ms, '
              f'{len(hits)} reused median {sorted(hits)[len(hits) // 2] * 1000:.1f} ms')
    print('Snapshot reuse read-after-write, finance grant/revoke, own-record privacy and revocation checks passed')


if __name__ == '__main__':
    main()
