// Quick smoke test for all 4 assistant endpoints
const http = require('http');

function post(path, body) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(body);
    const opts = {
      hostname: 'localhost', port: 4000,
      path, method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data) }
    };
    const req = http.request(opts, res => {
      let raw = '';
      res.setEncoding('utf8');
      res.on('data', c => raw += c);
      res.on('end', () => resolve(JSON.parse(raw)));
    });
    req.on('error', reject);
    req.write(data);
    req.end();
  });
}

async function run() {
  const endpoints = ['sdr', 'dentist', 'support', 'delivery'];
  for (const ep of endpoints) {
    try {
      const start = await post(`/api/${ep}/start`, {});
      console.log(`\n✅ ${ep.toUpperCase()} /start`);
      console.log('  sessionId:', start.sessionId);
      console.log('  prompt:', start.prompt);

      // Send one message
      const msg = await post(`/api/${ep}/message`, {
        sessionId: start.sessionId,
        message: 'Привет тест'
      });
      console.log(`  /message nextPrompt: ${msg.nextPrompt ?? '(null)'}`);
      console.log(`  completed: ${msg.completed}`);
    } catch (e) {
      console.log(`❌ ${ep} error:`, e.message);
    }
  }
}
run();
