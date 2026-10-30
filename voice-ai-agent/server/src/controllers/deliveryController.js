const createAssistantController = require('./createAssistantController');
const deliveryFlow = require('../flows/deliveryFlow');

module.exports = createAssistantController('delivery', deliveryFlow);
