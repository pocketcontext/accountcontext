#!/usr/bin/env python3
"""Exercise AccountContext through HTTP against an isolated temporary database."""
import argparse
import concurrent.futures
import contextlib
import json
from pathlib import Path
import socket
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]

@contextlib.contextmanager
def server(binary):
    with tempfile.TemporaryDirectory(prefix='accountcontext-test-') as tmp:
        hooks=Path(tmp)/'pb_hooks'
        shutil.copytree(ROOT/'pb_hooks',hooks)
        (hooks/'failure_fixture.pb.js').write_text('''
onRecordCreateExecute((e) => {
  if(e.record.getString('record') === 'auditfailure001') throw new Error('Synthetic audit failure');
  e.next();
}, 'audit_log');
onRecordCreateExecute((e) => {
  if(e.record.id === 'dirfailure00001') throw new Error('Synthetic directory failure');
  e.next();
}, 'user_directory');
''')
        common = [str(Path(binary).resolve()), '--dir', str(Path(tmp)/'pb_data'), '--migrationsDir', str(ROOT/'pb_migrations'), '--hooksDir', str(hooks)]
        result = subprocess.run(common+['superuser','upsert','admin@example.com','SyntheticAdminPassword123!'],cwd=ROOT,capture_output=True,text=True)
        assert result.returncode == 0, result.stdout+result.stderr
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
        with open(Path(tmp)/'server.log','w+') as log:
            proc=subprocess.Popen(common+['serve','--http',f'127.0.0.1:{port}'],cwd=ROOT,stdout=log,stderr=log)
            def request(method,path,body=None,token=None,expected=200):
                headers={'Content-Type':'application/json'}
                if token: headers['Authorization']=token
                req=urllib.request.Request(f'http://127.0.0.1:{port}'+path,data=None if body is None else json.dumps(body).encode(),headers=headers,method=method)
                try:
                    with urllib.request.urlopen(req,timeout=20) as r: status,raw=r.status,r.read()
                except urllib.error.HTTPError as e: status,raw=e.code,e.read()
                assert status in (expected if isinstance(expected,tuple) else (expected,)), (method,path,status,raw.decode())
                return json.loads(raw) if raw else None
            try:
                for _ in range(150):
                    try: request('GET','/api/health'); break
                    except (OSError,AssertionError):
                        if proc.poll() is not None: log.seek(0); raise AssertionError(log.read())
                        time.sleep(.1)
                else: raise AssertionError('Server startup timed out')
                request.base_url = f'http://127.0.0.1:{port}'
                request.data_dir = Path(tmp)/'pb_data'
                yield request
            finally:
                proc.terminate();proc.wait(timeout=15)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--binary',required=True);args=parser.parse_args()
    with server(args.binary) as request:
        p=lambda t:'/api/collections/'+t+'/records'
        admin=request('POST','/api/collections/_superusers/auth-with-password',{'identity':'admin@example.com','password':'SyntheticAdminPassword123!'})['token']
        def account(email):
            u=request('POST',p('users'),{'email':email,'name':email,'password':'SyntheticUserPassword123!','passwordConfirm':'SyntheticUserPassword123!'},admin)
            tok=request('POST','/api/collections/users/auth-with-password',{'identity':email,'password':'SyntheticUserPassword123!'})['token'];return u,tok
        u,token=account('finance@example.com');other,ot=account('claimant@example.com');foreign,ft=account('foreign@example.com')
        request('POST',p('finance_members'),{'account':u['id'],'can_approve':True},admin)
        def create(t,b,tok=token,status=200):return request('POST',p(t),b,tok,status)
        def patch(t,r,b,tok=token,status=200):return request('PATCH',p(t)+'/'+r['id'],dict(expected_revision=r['revision'],**b),tok,status)
        def sql(q,tok=token):
            result=request('POST','/api/context/query',{'sql':q},tok);return [dict(zip(result['columns'],row)) if isinstance(row,list) else row for row in result['rows']]
        def upload(owner,tok,title='Synthetic invoice'):
            boundary='accountcontext-test-boundary'; content=b'Original synthetic invoice\n'
            body=(f'--{boundary}\r\nContent-Disposition: form-data; name="title"\r\n\r\n{title}\r\n--{boundary}\r\nContent-Disposition: form-data; name="owner"\r\n\r\n{owner}\r\n--{boundary}\r\nContent-Disposition: form-data; name="original"; filename="invoice.txt"\r\nContent-Type: text/plain\r\n\r\n').encode()+content+f'\r\n--{boundary}--\r\n'.encode()
            req=urllib.request.Request(request.base_url+p('documents'),body,{'Content-Type':'multipart/form-data; boundary='+boundary,'Authorization':tok},method='POST')
            try:
                with urllib.request.urlopen(req) as r:doc=json.load(r)
            except urllib.error.HTTPError as e:raise AssertionError(e.read().decode())
            import hashlib
            assert doc['sha256']==hashlib.sha256(content).hexdigest(),doc
            return doc,content
        doc,content=upload(other['id'],ot)
        assert len(sql('SELECT * FROM documents',ot))==1 and sql('SELECT * FROM documents',ft)==[]
        request('GET',p('documents')+'/'+doc['id'],token=ot,expected=404)
        request('PATCH',p('documents')+'/'+doc['id'],{'expected_revision':1,'title':'overwrite'},admin,(400,403))
        def file_get(tok,expected):
            ftok=request('POST','/api/files/token',{},tok)['token'] if tok else ''
            url=request.base_url+'/api/files/'+doc['collectionId']+'/'+doc['id']+'/'+doc['original']+'?token='+ftok
            try:
                with urllib.request.urlopen(url) as r: status,data=r.status,r.read()
            except urllib.error.HTTPError as e:status,data=e.code,e.read()
            assert status==expected,(status,data)
            if expected==200:assert data==content
        file_get(ot,200);file_get(ft,404);file_get(None,404);file_get(token,200)
        claim=create('claims',{'owner':other['id'],'document':doc['id'],'title':'Founder purchase','payer':'Synthetic founder','currency':'USD','currency_exponent':2,'amount_minor':10000,'business_purpose':'Synthetic service','status':'draft'},ot)
        create('claims',{'owner':other['id'],'title':'Spoof','currency':'USD','currency_exponent':2,'amount_minor':100,'status':'draft'},ft,403)
        assert sql('SELECT * FROM claims',ft)==[]
        claim=patch('claims',claim,{'status':'submitted'},ot)
        patch('claims',claim,{'status':'approved'},ot,403)
        claim=patch('claims',claim,{'status':'approved'})
        patch('claims',claim,{'amount_minor':1},token,400)
        party=create('parties',{'name':'Synthetic Company'})
        vendors=[]
        for name in ['Google Workspace','Namecheap','Claude Code','LinkedIn Ads','Google Ads','Reddit Ads']:vendors.append(create('parties',{'name':name}))
        create('parties',{'name':'No finance'},ot,(400,403))
        updated=patch('parties',party,{'details':'Changed'});patch('parties',party,{'details':'Stale'},token,409)
        bill=create('bills',{'supplier':vendors[0]['id'],'billed_party':party['id'],'document':doc['id'],'number':'SYN-001','kind':'invoice','issue_date':'2026-09-25 00:00:00Z','currency':'USD','currency_exponent':2,'net_minor':8000,'tax_minor':2000,'gross_minor':10000,'business_purpose':'Synthetic business','status':'draft'})
        create('bill_lines',{'bill':bill['id'],'description':'Synthetic line','net_minor':8000,'tax_minor':2000,'gross_minor':10000})
        wrong_account=create('billing_accounts',{'supplier':vendors[1]['id'],'billed_party':party['id'],'label':'Other vendor'})
        patch('bills',bill,{'billing_account':wrong_account['id']},token,400)
        bill=patch('bills',bill,{'status':'reviewed'})
        patch('bills',bill,{'gross_minor':9999},token,400)
        pay=create('payments',{'payer':party['id'],'currency':'EUR','currency_exponent':2,'amount_minor':9000,'fee_minor':20,'direction':'outgoing','status':'recorded'})
        allocation={'bill':bill['id'],'payment':pay['id'],'bill_minor':5000,'payment_minor':4500,'status':'recorded'}
        create('payment_allocations',allocation,token,400)
        allocation.update(fx_rate='0.90',fx_date='2026-09-25 00:00:00Z',fx_source='Synthetic bank')
        a=create('payment_allocations',allocation);create('payment_allocations',allocation)
        create('payment_allocations',allocation,token,400)
        patch('payments',pay,{'status':'void','void_reason':'test'},token,400)
        patch('bills',bill,{'status':'void','void_reason':'test'},token,400)
        create('claim_reimbursements',{'claim':claim['id'],'payment':pay['id'],'claim_minor':100,'payment_minor':90,'fx_rate':'0.90','fx_date':'2026-09-25 00:00:00Z','fx_source':'bank','status':'recorded'},token,400)
        usd=create('payments',{'currency':'USD','currency_exponent':2,'amount_minor':10000,'direction':'outgoing','status':'recorded'})
        create('claim_reimbursements',{'claim':claim['id'],'payment':usd['id'],'claim_minor':10000,'payment_minor':10000,'status':'recorded'})
        assert len(sql('SELECT * FROM claim_reimbursements',ot))==1
        assert sql('SELECT * FROM claim_reimbursements',ft)==[]
        assert sql('SELECT * FROM payments',ot)==[]
        create('import_batches',{'source':'synthetic.csv','sha256':'a'*64});create('import_batches',{'source':'again.csv','sha256':'a'*64},token,400)
        create('export_batches',{'name':'test','status':'preparing'},ot,(400,403))
        assert sql('SELECT * FROM parties',ot)==[]
        assert sql('SELECT * FROM audit_log',ot) and all(row['owner']==other['id'] for row in sql('SELECT * FROM audit_log',ot))
        request('POST','/api/context/query',{'sql':'SELECT * FROM finance_members'},token,400)
        request('POST','/api/context/query',{'sql':'SELECT * FROM users'},token,400)
        request('GET',p('bills')+'/'+bill['id']+'?expand=supplier,document',token=token,expected=(403,404))
        before=len(sql('SELECT * FROM parties'))
        request('POST','/api/batch',{'requests':[{'method':'POST','url':p('parties'),'body':{'name':'Rollback'}},{'method':'POST','url':p('payments'),'body':{'currency':'USD','currency_exponent':2,'amount_minor':1.5,'direction':'outgoing','status':'recorded'}}]},token,400)
        assert len(sql('SELECT * FROM parties'))==before
        # Audit failure rolls back the business record inside the writer transaction.
        create('parties',{'id':'auditfailure001','name':'Audit rollback'},token,(400,500))
        assert sql("SELECT id FROM parties WHERE id = 'auditfailure001'")==[]
        patch('bills',bill,{'status':'draft'},token,400)
        patch('claims',claim,{'status':'draft'},token,400)
        # Concurrent writers cannot reuse the same revision.
        def race_update(i):return patch('parties',updated,{'details':str(i)},token,(200,409))
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool: result=list(pool.map(race_update,range(2)))
        assert sum('id' in r for r in result)==1
        # Credit notes and refunds remain separate from outgoing settlements.
        credit=create('bills',{'supplier':vendors[0]['id'],'billed_party':party['id'],'document':doc['id'],'number':'SYN-CREDIT','kind':'credit_note','correction_of':bill['id'],'issue_date':'2026-09-25 00:00:00Z','currency':'USD','currency_exponent':2,'net_minor':1600,'tax_minor':400,'gross_minor':2000,'business_purpose':'Synthetic refund','status':'reviewed'})
        refund=create('payments',{'currency':'USD','currency_exponent':2,'amount_minor':2000,'direction':'refund','status':'recorded'})
        refundalloc={'bill':credit['id'],'payment':refund['id'],'bill_minor':1500,'payment_minor':1500,'status':'recorded'}
        def race_allocate(i):return create('payment_allocations',refundalloc,token,(200,400))
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool: result=list(pool.map(race_allocate,range(2)))
        assert sum('id' in r for r in result)==1
        create('payment_allocations',dict(refundalloc,bill_minor=500,payment_minor=501),token,400)
        create('payments',{'currency':'USD','currency_exponent':0,'amount_minor':10,'direction':'outgoing','status':'recorded'},token,400)
        create('payments',{'currency':'USD','currency_exponent':2,'amount_minor':9007199254740992,'direction':'outgoing','status':'recorded'},token,400)
        # Allocation rounding permits at most one explicit settlement minor unit.
        rounding=create('payments',{'currency':'EUR','currency_exponent':2,'amount_minor':450,'direction':'refund','status':'recorded'})
        roundpayload={'bill':credit['id'],'payment':rounding['id'],'bill_minor':500,'payment_minor':449,'fx_rate':'0.9','fx_date':'2026-09-25 00:00:00Z','fx_source':'Synthetic card rounding','status':'recorded'}
        create('payment_allocations',dict(roundpayload,payment_minor=447),token,400)
        create('payment_allocations',roundpayload)
        role=request('GET',p('finance_members'),token=admin)['items'][0]
        request('DELETE',p('finance_members')+'/'+role['id'],token=admin,expected=204)
        assert sql('SELECT * FROM bills')==[]
        file_get(token,404)
        # Real SSE connections: admin is a positive delivery control; ordinary
        # subscriptions must never bypass the locked REST read policies.
        import queue
        import threading
        def subscriber(auth):
            messages=queue.Queue()
            def listen():
                try:
                    with urllib.request.urlopen(request.base_url+'/api/realtime',timeout=10) as response:
                        event,data='',''
                        for raw in response:
                            line=raw.decode().strip()
                            if line.startswith('event:'):event=line[6:].strip()
                            elif line.startswith('data:'):data=line[5:].strip()
                            elif not line and event:
                                messages.put((event,json.loads(data)));event,data='',''
                except Exception as exc:messages.put(('error',str(exc)))
            threading.Thread(target=listen,daemon=True).start()
            event,data=messages.get(timeout=5)
            assert event=='PB_CONNECT',(event,data)
            subscription={'clientId':data['clientId'],'subscriptions':['claims/*','documents/*','audit_log/*']}
            request('POST','/api/realtime',subscription,auth,expected=204)
            return messages,subscription
        visible,control=subscriber(admin)
        hidden,subscription=subscriber(ot)
        liveclaim=create('claims',{'owner':foreign['id'],'title':'Foreign SSE claim','currency':'USD','currency_exponent':2,'amount_minor':100,'status':'draft'},ft)
        livefile,_=upload(foreign['id'],ft,'Foreign SSE original')
        seen=set()
        for _ in range(8):
            event,data=visible.get(timeout=5)
            assert event!='error',(event,data)
            seen.add((data.get('record',{}).get('collectionName'),data.get('record',{}).get('id')))
            if ('claims',liveclaim['id']) in seen and ('documents',livefile['id']) in seen and any(t=='audit_log' for t,i in seen):break
        assert ('claims',liveclaim['id']) in seen and ('documents',livefile['id']) in seen
        try:raise AssertionError(('Ordinary subscriber received financial event',hidden.get(timeout=.4)))
        except queue.Empty:pass
        saved_file_token=request('POST','/api/files/token',{},ot)['token']
        request('PATCH',p('users')+'/'+other['id'],{'disabled':True},admin)
        saved_url=request.base_url+'/api/files/'+doc['collectionId']+'/'+doc['id']+'/'+doc['original']+'?token='+saved_file_token
        try: urllib.request.urlopen(saved_url);raise AssertionError('Disabled file token accepted')
        except urllib.error.HTTPError as exc: assert exc.code in (401,403,404)
        request('POST','/api/context/query',{'sql':'SELECT * FROM claims'},ot,(401,403))
        request('POST','/api/realtime',subscription,ot,expected=401)
    print('AccountContext integration and document security checks passed')
if __name__=='__main__':main()
