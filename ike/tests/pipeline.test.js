// tests/pipeline.test.js
const { analyzeChannel } = require('../src/pipeline/analysis');

test('analyzeChannel returns mock analytics object', async () => {
  const data = await analyzeChannel('test-channel');
  expect(data).toHaveProperty('channelId', 'test-channel');
  expect(data).toHaveProperty('subscriberCount');
  expect(data).toHaveProperty('averageWatchTime');
});
