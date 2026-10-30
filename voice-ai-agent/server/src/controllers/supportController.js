const createAssistantController = require('./createAssistantController');
const supportFlow = require('../flows/supportFlow');

module.exports = createAssistantController('support', supportFlow);
