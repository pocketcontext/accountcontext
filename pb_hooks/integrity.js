function invalid(m){throw new BadRequestError(m);}
function rows(app,t,f,p){return app.findRecordsByFilter(t,f,'',0,0,p||{});}
function member(app,id){return rows(app,'finance_members','account = {:id}',{id})[0];}
function same(r,old,k){return JSON.stringify(r.get(k))===JSON.stringify(old.get(k));}
function sum(list,k){let n=0;for(const r of list){n+=r.getFloat(k);if(!Number.isSafeInteger(n))invalid('Amount total exceeds safe integer bound');}return n;}
function active(app,t,k,id,except){return rows(app,t,k+' = {:id} && status = "recorded" && id != {:except}',{id,except:except||''});}
function money(r,k){const n=r.getFloat(k);if(!Number.isSafeInteger(n)||n<0)invalid(k+' must be a nonnegative safe integer');}
function fx(r,left,right,leftAmount,rightAmount){
 const a=r.getFloat(leftAmount),b=r.getFloat(rightAmount);if(a<=0||b<=0)invalid('Allocations must be positive');
 if(left.getString('currency')===right.getString('currency')){if(left.getInt('currency_exponent')!==right.getInt('currency_exponent')||a!==b)invalid('Same-currency allocations must match');}
 else {
  const rate=Number(r.getString('fx_rate'));if(!Number.isFinite(rate)||rate<=0||!r.getString('fx_date')||!r.getString('fx_source'))invalid('Cross-currency allocations require positive rate, date and source');
  const calculated=a/Math.pow(10,left.getInt('currency_exponent'))*rate*Math.pow(10,right.getInt('currency_exponent'));
  if(!Number.isSafeInteger(Math.round(calculated))||Math.abs(Math.round(calculated)-b)>1)invalid('FX allocation differs from documented rate by more than one minor unit');
 }
}
function validate(app,r){
 const t=r.collection().name,old=r.original(),fresh=r.isNew();
 for(const f of r.collection().fields.fieldNames())if(f.endsWith('_minor'))money(r,f);
 if(r.collection().fields.getByName('currency')){
  const currency=r.getString('currency'), exp=r.getInt('currency_exponent');
  const expected={USD:2,EUR:2,GBP:2,JPY:0,KWD:3,CHF:2,CAD:2,AUD:2,INR:2};
  if(expected[currency]===undefined)invalid('Unsupported currency; add an explicit reviewed exponent policy first');
  if(exp!==expected[currency])invalid('currency_exponent must match currency');
 }
 if(!fresh){
  for(const k of ['created_by','created','owner'])if(r.collection().fields.getByName(k)&&!same(r,old,k))invalid(k+' is immutable');
  if(old.getString('status')==='void' && r.getString('status')!=='void')invalid('Voided records cannot be restored');
  const immutable=['payments','payment_allocations','claim_reimbursements','import_batches'].includes(t);
  if(immutable)for(const k of r.collection().fields.fieldNames())if(!['status','void_reason','updated','updated_by','revision'].includes(k)&&!same(r,old,k))invalid(k+' is immutable; void and replace');
 }
 if(!fresh&&t==='bills'&&old.getString('status')==='reviewed'&&!['reviewed','void'].includes(r.getString('status')))invalid('Reviewed bills can only be voided');
 if(!fresh&&t==='claims'&&r.getString('status')!==old.getString('status')){const allowed={draft:['submitted'],submitted:['approved','rejected','void'],approved:['void'],rejected:['void'],void:[]};if(!(allowed[old.getString('status')]||[]).includes(r.getString('status')))invalid('Invalid claim status transition');}
 if(r.getString('status')==='void' && t!=='claims' && !r.getString('void_reason'))invalid('Voiding requires a reason');
 if(t==='documents'&&!fresh)invalid('Original documents are immutable');
 if(t==='bills'||t==='bill_lines'){
  if(r.getFloat('net_minor')+r.getFloat('tax_minor')!==r.getFloat('gross_minor')||!Number.isSafeInteger(r.getFloat('net_minor')+r.getFloat('tax_minor')))invalid('Net plus tax must equal gross');
 }
 if((t==='bills'||t==='subscriptions')&&r.getString('billing_account')){
  const account=app.findRecordById('billing_accounts',r.getString('billing_account'));
  if(account.getString('supplier')!==r.getString('supplier'))invalid('Billing account supplier must match');
  if(t==='bills'&&account.getString('billed_party')&&r.getString('billed_party')&&account.getString('billed_party')!==r.getString('billed_party'))invalid('Billing account billed party must match');
 }
 if(t==='bills'){
  if(r.getString('correction_of')){if(r.getString('correction_of')===r.id)invalid('Correction cannot refer to itself');app.findRecordById('bills',r.getString('correction_of'));}
  if(r.getString('service_start')&&r.getString('service_end')&&r.getString('service_end')<r.getString('service_start'))invalid('Service period is reversed');
  if(!fresh&&old.getString('status')==='reviewed')for(const k of r.collection().fields.fieldNames())if(!['status','void_reason','updated','updated_by','revision'].includes(k)&&!same(r,old,k))invalid('Reviewed bills require a void and correction record');
  const allocations=active(app,'payment_allocations','bill',r.id);
  if(allocations.length&&(r.getString('status')!=='reviewed'||!same(r,old,'currency')||sum(allocations,'bill_minor')>r.getFloat('gross_minor')))invalid('Void allocations before changing settled bill');
  if(r.getString('kind')==='credit_note'){
   if(!r.getString('correction_of'))invalid('Credit notes require original bill reference in correction_of');
   const source=app.findRecordById('bills',r.getString('correction_of'));
   if(source.getString('kind')==='credit_note'||source.getString('status')!=='reviewed'||source.getString('currency')!==r.getString('currency')||source.getString('supplier')!==r.getString('supplier'))invalid('Credit note must reference reviewed bill with matching supplier and currency');
   if(r.getString('status')!=='void'){
    const credits=rows(app,'bills','correction_of = {:source} && kind = "credit_note" && status != "void" && id != {:id}',{source:source.id,id:r.id});
    const total=sum(credits,'gross_minor')+r.getFloat('gross_minor');if(!Number.isSafeInteger(total)||total>source.getFloat('gross_minor'))invalid('Credits exceed original bill');
   }
  }
  if(r.getString('status')==='void'&&rows(app,'bills','correction_of = {:id} && kind = "credit_note" && status != "void"',{id:r.id}).length)invalid('Void credit notes before original bill');
  if(r.getString('status')==='reviewed'){
   if(!r.getString('document')||!r.getString('issue_date')||!r.getString('billed_party')||!r.getString('business_purpose'))invalid('Review requires original, issue date, billed party and purpose');
   const lines=rows(app,'bill_lines','bill = {:id}',{id:r.id});if(lines.length)for(const k of ['net_minor','tax_minor','gross_minor'])if(sum(lines,k)!==r.getFloat(k))invalid('Line totals must match reviewed bill');
  }
 }
 if(t==='bill_lines'){const b=app.findRecordById('bills',r.getString('bill'));if(b.getString('status')!=='draft')invalid('Only draft bill lines can change');if(!fresh&&!same(r,old,'bill'))invalid('Bill line parent is immutable');}
 if(t==='payments'){
  if(r.getFloat('amount_minor')<=0)invalid('Payment must be positive');
  if(r.getString('status')==='void'&&(active(app,'payment_allocations','payment',r.id).length||active(app,'claim_reimbursements','payment',r.id).length))invalid('Void allocations before payment');
 }
 if(t==='payment_allocations'||t==='claim_reimbursements'){
  const p=app.findRecordById('payments',r.getString('payment')),isBill=t==='payment_allocations',left=app.findRecordById(isBill?'bills':'claims',r.getString(isBill?'bill':'claim')),key=isBill?'bill_minor':'claim_minor';
  fx(r,left,p,key,'payment_minor');
  if(r.getString('status')==='recorded'){
   if(p.getString('status')!=='recorded'||left.getString('status')!==(isBill?'reviewed':'approved'))invalid('Allocation requires recorded payment and reviewed bill or approved claim');
   if(p.getString('direction')!==(isBill&&left.getString('kind')==='credit_note'?'refund':'outgoing'))invalid('Payment direction does not match expense/refund');
   const used=sum(active(app,'payment_allocations','payment',p.id,r.id),'payment_minor')+sum(active(app,'claim_reimbursements','payment',p.id,r.id),'payment_minor')+r.getFloat('payment_minor');
   if(!Number.isSafeInteger(used)||used>p.getFloat('amount_minor'))invalid('Payment overallocated');
   const consumed=sum(active(app,t,isBill?'bill':'claim',left.id,r.id),key)+r.getFloat(key);
   if(!Number.isSafeInteger(consumed)||consumed>left.getFloat(isBill?'gross_minor':'amount_minor'))invalid('Expense overallocated');
  }
 }
 if(t==='claims'){
  if(r.getFloat('amount_minor')<=0)invalid('Claim must be positive');
  if(r.getString('status')!=='draft'&&(!r.getString('document')||!r.getString('business_purpose')||!r.getString('payer')))invalid('Submitted claims require original, payer and purpose');
  if(!fresh&&old.getString('status')!=='draft')for(const k of r.collection().fields.fieldNames())if(!['status','decision_note','updated','updated_by','revision'].includes(k)&&!same(r,old,k))invalid('Submitted claim evidence and amounts are immutable');
  if(!fresh&&old.getString('status')==='approved'&&r.getString('status')!=='approved'&&active(app,'claim_reimbursements','claim',r.id).length)invalid('Void reimbursements before changing approval');
  if(r.getString('status')==='approved'&&old.getString('status')!=='approved'&&old.getString('status')!=='submitted')invalid('Only submitted claims may be approved');
  if(['rejected','void'].includes(r.getString('status'))&&!r.getString('decision_note'))invalid('Decision requires a note');
 }
}
function write(e){
 const original=e.app,r=e.record,t=r.collection().name,fresh=r.isNew(),body=e.requestInfo().body;
 original.runInTransaction(app=>{e.app=app;try{
 const user=e.auth&&e.auth.collection().name==='users'?e.auth.id:'',finance=user?member(app,user):null,operator=e.auth&&e.auth.collection().name==='_superusers';
 if(!operator&&!user)throw new ForbiddenError('Authentication required');
 if(!operator&&!finance&&!['claims','documents'].includes(t))throw new ForbiddenError('Finance access required');
 if(!fresh){const current=app.findRecordById(t,r.id);const expected=Number(body.expected_revision);if(body.expected_revision===undefined||!Number.isInteger(expected))invalid('expected_revision required');if(current.getInt('revision')!==expected||current.getInt('revision')!==r.original().getInt('revision'))throw new ApiError(409,'Revision conflict',{});}
 for(const k of ['revision','created_by','updated_by','created','updated'].concat(t==='documents'?['sha256']:[]))if(Object.prototype.hasOwnProperty.call(body,k))invalid(k+' is server managed');
 if(t==='documents'||t==='claims'){
  if(fresh&&!r.getString('owner'))r.set('owner',user);
  if(!operator&&!finance&&r.getString('owner')!==user)throw new ForbiddenError('Only your own claims and documents');
 }
 if(t==='claims'){
  if(['approved','rejected'].includes(r.getString('status'))&&r.getString('status')!==r.original().getString('status')&&!operator&&(!finance||!finance.getBool('can_approve')))throw new ForbiddenError('Approval authority required');
  if(!operator&&!finance&&!['draft','submitted'].includes(r.getString('status')))throw new ForbiddenError('Claimants may draft or submit only');
  if(fresh&&r.getString('status')!=='draft')invalid('New claims must start as drafts');
 }
 const doc=r.getString('document');if(doc){const d=app.findRecordById('documents',doc);if(t==='claims'&&d.getString('owner')!==r.getString('owner'))invalid('Claim document must belong to claimant');}
 r.set('_audit_actor',user?'user:'+user:'superuser:'+e.auth.id);r.set('revision',fresh?1:r.original().getInt('revision')+1);r.set('created_by',fresh?user:r.original().getString('created_by'));r.set('updated_by',user);
 e.next();
 }finally{e.app=original;}});
}
function snapshot(r){const all=JSON.parse(JSON.stringify(r)),out={};for(const f of r.collection().fields.fieldNames())out[f]=all[f];return out;}
function audit(e,action){
 const actor=e.record.getString('_audit_actor');if(!actor)return e.next();e.record.set('_audit_actor','');const before=action==='update'?snapshot(e.record.original()):null;
 e.next();
 if(e.record.collection().name==='documents'&&action==='create'){
  const path=e.app.dataDir()+'/storage/'+e.record.collection().id+'/'+e.record.id+'/'+e.record.getString('original');
  const hash=toString($os.cmd('sha256sum',path).output()).split(' ')[0];if(!/^[a-f0-9]{64}$/.test(hash))invalid('Cannot hash original');
  e.record.set('sha256',hash);e.app.saveNoValidate(e.record);
 }
 const after=snapshot(e.record),changes=action==='create'?{after}:{before:{},after:{}};
 if(before)for(const k in after)if(JSON.stringify(before[k])!==JSON.stringify(after[k])){changes.before[k]=before[k];changes.after[k]=after[k];}
 const row=new Record(e.app.findCollectionByNameOrId('audit_log'));row.set('action',action);row.set('collection',e.record.collection().name);row.set('record',e.record.id);row.set('actor_type',actor.split(':')[0]);row.set('actor',actor.split(':')[1]);row.set('owner',e.record.collection().name==='claim_reimbursements'?e.app.findRecordById('claims',e.record.getString('claim')).getString('owner'):e.record.getString('owner'));row.set('changes',changes);e.app.save(row);
}
module.exports={write,validate,audit};
