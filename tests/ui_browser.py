#!/usr/bin/env python3
"""Production reader browser tests against isolated synthetic records."""
import argparse, contextlib, json, os, pathlib, shutil, subprocess, tempfile, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PASSWORD='SyntheticUserPassword123!'
ROOT=pathlib.Path(__file__).resolve().parents[1]

@contextlib.contextmanager
def control_server(action):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            action(self.path);self.send_response(200);self.end_headers();self.wfile.write(b'{}')
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield 'http://127.0.0.1:'+str(server.server_port)
    finally:server.shutdown();server.server_close();thread.join()

def browser(base, fixture, action):
    with tempfile.TemporaryDirectory(prefix='reader-browser-') as temp, control_server(action) as controller:
        path=pathlib.Path(temp)/'fixture.json';path.write_text(json.dumps(fixture));path.chmod(0o600)
        env=dict(os.environ,READER_SCREENSHOT_DIR=os.environ.get('READER_SCREENSHOT_DIR',temp),READER_TEST_URL=base,READER_TEST_FIXTURE=str(path),READER_TEST_CONTROL=controller,READER_TEST_OUTPUT=str(pathlib.Path(temp)/'results'))
        result=subprocess.run(['pnpm','e2e'],cwd=ROOT/'ui',env=env)
        if result.returncode:raise SystemExit(result.returncode)

def run(binary):
    from integration import server
    import urllib.request
    with server(binary) as request:
        path=lambda table:'/api/collections/'+table+'/records'
        op=request('POST','/api/collections/_superusers/auth-with-password',{'identity':'admin@example.com','password':'SyntheticAdminPassword123!'})['token']
        def account(email):
            user=request('POST',path('users'),dict(email=email,name='Reader',password=PASSWORD,passwordConfirm=PASSWORD),op)
            token=request('POST','/api/collections/users/auth-with-password',{'identity':email,'password':PASSWORD})['token'];return user,token
        user,token=account('reader@example.com');finance,ft=account('finance@example.com')
        request('POST',path('finance_members'),{'account':finance['id'],'can_approve':True},op)
        create=lambda table,body,tok=token:request('POST',path(table),body,tok)
        records=[create('claims',{'owner':user['id'],'title':f'Fixture claim {i:02}','currency':'USD','currency_exponent':2,'amount_minor':100,'status':'draft'}) for i in range(35)]
        first=records[0]
        boundary='reader-fixture';body=(f'--{boundary}\r\nContent-Disposition: form-data; name="title"\r\n\r\nReadable original evidence\r\n--{boundary}\r\nContent-Disposition: form-data; name="owner"\r\n\r\n{user["id"]}\r\n--{boundary}\r\nContent-Disposition: form-data; name="original"; filename="fixture.txt"\r\nContent-Type: text/plain\r\n\r\nSynthetic original\r\n--{boundary}--\r\n').encode()
        req=urllib.request.Request(request.base_url+path('documents'),body,{'Content-Type':'multipart/form-data; boundary='+boundary,'Authorization':token})
        with urllib.request.urlopen(req) as response:doc=json.load(response)
        first=request('PATCH',path('claims')+'/'+first['id'],{'expected_revision':first['revision'],'document':doc['id'],'payer':'Synthetic employee','business_purpose':'Synthetic evidence'},token)
        first=request('PATCH',path('claims')+'/'+first['id'],{'expected_revision':first['revision'],'status':'submitted'},token)
        first=request('PATCH',path('claims')+'/'+first['id'],{'expected_revision':first['revision'],'status':'approved'},ft)
        payment=create('payments',{'currency':'USD','currency_exponent':2,'amount_minor':100,'status':'recorded','direction':'outgoing'},ft)
        allocation=create('claim_reimbursements',{'claim':first['id'],'payment':payment['id'],'claim_minor':100,'payment_minor':100,'status':'recorded'},ft)
        fixture=dict(email='reader@example.com',password=PASSWORD,table='claims',label='Claims',id=first['id'],title=first['title'],needle=records[-1]['title'],forbiddenTable='payments',forbiddenId=payment['id'],forbiddenText=payment['id'],relationTitle='Readable original evidence',relationTable='documents',relationId=doc['id'],fileTable='documents',fileId=doc['id'],allocationId=allocation['id'])
        def action(action):
            if action=='/revoke':request('PATCH',path('users')+'/'+user['id'],{'disabled':True},op)
        browser(request.base_url,fixture,action)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--binary',required=True);args=parser.parse_args()
    run(args.binary)
