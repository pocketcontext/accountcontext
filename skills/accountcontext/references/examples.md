# CLI examples

Set `ACCOUNTCONTEXT_URL=https://accounts.pocketcontext.com` and `ACCOUNTCONTEXT_USER_EMAIL` to your Workspace email. Substitute the installed absolute client path and actual record IDs below.

```sh
python3 /absolute/path/accountcontext/scripts/ac.py login --google
python3 /absolute/path/accountcontext/scripts/ac.py whoami
python3 /absolute/path/accountcontext/scripts/ac.py check
python3 /absolute/path/accountcontext/scripts/ac.py query 'SELECT id,name FROM parties ORDER BY name'
python3 /absolute/path/accountcontext/scripts/ac.py create parties '{"name":"Google Workspace","kind":"supplier"}'
python3 /absolute/path/accountcontext/scripts/ac.py upload invoice.pdf '{"owner":"USER_RECORD_ID","title":"Workspace invoice"}'
python3 /absolute/path/accountcontext/scripts/ac.py report
python3 /absolute/path/accountcontext/scripts/ac.py export accountant.zip
```

For an SSH client, connect with `ssh -L 8765:127.0.0.1:8765 user@host` and open the printed Google URL in the laptop browser. The identity returned must match `ACCOUNTCONTEXT_USER_EMAIL`.

CSV format, with JSON quote escaping:

```csv
collection,json
parties,"{""name"":""Namecheap"",""kind"":""supplier""}"
```

`newid` generates an ID for multi-record batches. `update COLLECTION ID JSON` requires `expected_revision`. `batch JSON` accepts up to 20 business creates/updates atomically. `get COLLECTION ID` reads through SQL. `download DOCUMENT_ID NEW_FILE` verifies the original checksum. Pass `-` as a JSON/SQL argument to consume standard input.

Google Workspace, Namecheap, Claude Code, LinkedIn Ads, Google Ads and Reddit Ads are ordinary suppliers, not integrations. No invoice amount or subscription is assumed from a supplier name.
