// server/src/routes/assistantRoutes.js
const express = require('express');
const router = express.Router();

const sdrController = require('../controllers/sdrController');
const dentistController = require('../controllers/dentistController');
const supportController = require('../controllers/supportController');
const deliveryController = require('../controllers/deliveryController');

router.post('/sdr/start', sdrController.startSession);
router.post('/sdr/message', sdrController.handleMessage);

router.post('/dentist/start', dentistController.startSession);
router.post('/dentist/message', dentistController.handleMessage);

router.post('/support/start', supportController.startSession);
router.post('/support/message', supportController.handleMessage);

router.post('/delivery/start', deliveryController.startSession);
router.post('/delivery/message', deliveryController.handleMessage);

module.exports = router;
