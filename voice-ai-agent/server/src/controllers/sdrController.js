const createAssistantController = require('./createAssistantController');
const sdrFlow = require('../flows/sdrFlow');

module.exports = createAssistantController('sdr', sdrFlow);
