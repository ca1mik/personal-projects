const assert=require('node:assert/strict'),E=require('./dist/engine.js');
let passed=0;function test(name,fn){fn();passed++;console.log('PASS '+name);}
function state(){return{requests:[{id:'a',date:'2026-11-01',start:'10:00',end:'18:00',duration:60,status:'waiting',created:1},{id:'b',date:'2026-11-01',start:'12:00',end:'18:00',duration:120,status:'waiting',created:2}],windows:[{id:'w',date:'2026-11-01',start:'15:00',end:'17:00',price:1800,status:'open'}],offers:[],bookings:[]};}
test('matching uses queue order',()=>assert.deepEqual(E.match(state(),state().windows[0],100).map(r=>r.id),['a','b']));
test('short window does not fit long session',()=>{const s=state();s.windows[0].end='16:00';assert.deepEqual(E.match(s,s.windows[0],100).map(r=>r.id),['a']);});
test('wrong date excluded',()=>{const s=state();s.requests[0].date='2026-11-02';assert.deepEqual(E.match(s,s.windows[0],100).map(r=>r.id),['b']);});
test('session must finish in client range',()=>{const s=state();s.requests[0].end='15:30';assert.deepEqual(E.match(s,s.windows[0],100).map(r=>r.id),['b']);});
test('one pending offer per slot',()=>{const s=state();E.offer(s,'w','a',100);assert.throws(()=>E.offer(s,'w','b',101));});
test('expiry releases slot and skips previous recipient',()=>{const s=state();E.offer(s,'w','a',100);assert.deepEqual(E.match(s,s.windows[0],100+900001).map(r=>r.id),['b']);});
test('cannot confirm expired offer',()=>{const s=state(),o=E.offer(s,'w','a',100);assert.throws(()=>E.resolve(s,o.id,'confirmed',900101));});
test('refusal advances to next client',()=>{const s=state(),o=E.offer(s,'w','a',100);E.resolve(s,o.id,'declined',101);assert.deepEqual(E.match(s,s.windows[0],102).map(r=>r.id),['b']);});
test('confirmation saves duration and remaining hour',()=>{const s=state(),o=E.offer(s,'w','a',100);E.resolve(s,o.id,'confirmed',101);assert.equal(s.bookings.length,1);assert.equal(s.bookings[0].end,'16:00');assert.equal(s.requests[0].status,'booked');assert.equal(s.windows[1].start,'16:00');assert.equal(s.windows[1].end,'17:00');});
test('repeated confirmation cannot double book',()=>{const s=state(),o=E.offer(s,'w','a',100);E.resolve(s,o.id,'confirmed',101);assert.throws(()=>E.resolve(s,o.id,'confirmed',102));assert.equal(s.bookings.length,1);});
test('overlapping confirmed booking is blocked',()=>{const s=state(),o=E.offer(s,'w','a',100);s.bookings.push({date:'2026-11-01',start:'15:30',end:'16:30'});assert.throws(()=>E.resolve(s,o.id,'confirmed',101));});
test('late client can use middle of a larger window',()=>{const s=state();s.requests[0].start='15:30';const o=E.offer(s,'w','a',100);assert.equal(o.start,'15:30');assert.equal(o.end,'16:30');E.resolve(s,o.id,'confirmed',101);assert.deepEqual(s.windows.filter(w=>w.status==='open').map(w=>[w.start,w.end]),[['15:00','15:30'],['16:30','17:00']]);});
console.log(`${passed} tests passed`);
