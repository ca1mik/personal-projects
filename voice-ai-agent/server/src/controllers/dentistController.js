const createAssistantController = require('./createAssistantController');
const dentistFlow = require('../flows/dentistFlow');

module.exports = createAssistantController('dentist', dentistFlow);
