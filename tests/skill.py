#!/usr/bin/env python3
"""Installed portable client exercises isolated evidence, imports and accountant export."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile
from integration import ROOT, server

parser=argparse.ArgumentParser();parser.add_argument('--binary',required=True);parser.add_argument('--write-schema',action='store_true');args=parser.parse_args()
with server(args.binary) as request,tempfile.TemporaryDirectory(prefix='accountcontext-skill-') as tmp:
    admin=request('POST','/api/collections/_superusers/auth-with-password',{'identity':'admin@example.com','password':'SyntheticAdminPassword123!'})['token']
    password='SyntheticSkillPassword123!'
    user=request('POST','/api/collections/users/records',{'email':'skill@example.com','name':'Synthetic skill','password':password,'passwordConfirm':password},admin)
    outsider=request('POST','/api/collections/users/records',{'email':'outsider@example.com','name':'Synthetic outsider','password':password,'passwordConfirm':password},admin)
    request('POST','/api/collections/finance_members/records',{'account':user['id'],'can_approve':True},admin)
    token=request('POST','/api/collections/users/auth-with-password',{'identity':'skill@example.com','password':password})['token']
    schema=request('GET','/api/context/schema',token=token)
    snapshot=ROOT/'skills/accountcontext/references/schema.json'
    if args.write_schema:snapshot.write_text(json.dumps(schema,indent=2)+'\n')
    assert json.loads(snapshot.read_text())==schema,'Schema changed; review and regenerate snapshot'
    skill=Path(tmp)/'portable';shutil.copytree(ROOT/'skills/accountcontext',skill)
    env={**os.environ,'HOME':tmp,'XDG_CACHE_HOME':str(Path(tmp)/'cache'),'ACCOUNTCONTEXT_URL':request.base_url,'ACCOUNTCONTEXT_USER_EMAIL':'skill@example.com','ACCOUNTCONTEXT_USER_PASSWORD':password}
    def cli(*argv,expected=0,email=None):
        local=dict(env)
        if email:local['ACCOUNTCONTEXT_USER_EMAIL']=email
        result=subprocess.run(['python3',str(skill/'scripts/ac.py'),*argv],env=local,cwd=tmp,capture_output=True,text=True)
        assert password not in result.stdout+result.stderr and token not in result.stdout+result.stderr
        assert result.returncode==expected,(argv,result.stdout,result.stderr)
        return result.stdout
    cli('whoami');cli('check')
    party=json.loads(cli('create','parties','{"name":"Synthetic vendor"}'))
    assert json.loads(cli('get','parties',party['id']))['name']=='Synthetic vendor'
    body=json.dumps({'name':'Updated synthetic vendor','expected_revision':party['revision']})
    cli('update','parties',party['id'],body);cli('update','parties',party['id'],body,expected=4)
    cli('update','parties',party['id'],'{"name":"No revision"}',expected=2)
    cli('batch',json.dumps([{'method':'POST','url':'/api/collections/users/records','body':{}}]),expected=2)
    original=Path(tmp)/'invoice.txt';original.write_bytes(b'Synthetic original invoice\n')
    doc=json.loads(cli('upload',str(original),json.dumps({'owner':user['id'],'title':'Synthetic invoice'})))
    assert doc['sha256']==hashlib.sha256(original.read_bytes()).hexdigest()
    downloaded=Path(tmp)/'downloaded.txt';cli('download',doc['id'],str(downloaded));assert downloaded.read_bytes()==original.read_bytes()
    cli('download',doc['id'],str(Path(tmp)/'stolen.txt'),email='outsider@example.com',expected=1)
    imports=Path(tmp)/'import.csv'
    with imports.open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['collection','json']);writer.writerow(['parties',json.dumps({'name':'Imported synthetic vendor'})])
    cli('import-csv',str(imports));cli('import-csv',str(imports),expected=1)
    cli('report')
    denied=Path(tmp)/'denied.zip';cli('export',str(denied),email='outsider@example.com',expected=1);assert not denied.exists()
    archive=Path(tmp)/'accountant.zip';cli('export',str(archive))
    with zipfile.ZipFile(archive) as z:
        manifest=json.loads(z.read('manifest.json'))
        originals=[entry for entry in manifest['files'] if entry['path'].startswith('originals/')]
        assert len(originals)==1 and z.read(originals[0]['path'])==original.read_bytes()
        for entry in manifest['files']:assert hashlib.sha256(z.read(entry['path'])).hexdigest()==entry['sha256']
    assert archive.stat().st_mode&0o777==0o600
    cli('logout')
print('Portable skill, schema, protected evidence, atomic imports and accountant export passed.')
