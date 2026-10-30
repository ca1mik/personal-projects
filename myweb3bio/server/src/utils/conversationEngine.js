// server/src/utils/conversationEngine.js
// Generic state-machine engine for script-driven AI conversations.
// Each "flow" is a plain JS object:
//
//   {
//     id: 'sdr',
//     steps: [
//       { id: 'greeting',  prompt: 'Привет! Как вас зовут?',  field: 'name',    validate: v => !!v.trim() },
//       { id: 'company',   prompt: 'Из какой вы компании?',   field: 'company', validate: v => !!v.trim() },
//       ...
//       { id: 'done', prompt: null }   // terminal step
//     ]
//   }
//
// startConversation(flow)  → session object
// handleUserMessage(session, message)  → result object

/**
 * Create a new conversation session from a flow definition.
 * @param {object} flow
 * @returns {object} session
 */
function startConversation(flow) {
  return {
    flow,
    stepIndex: 0,
    collectedData: {},
    completed: false,
    prompt: flow.steps[0]?.prompt ?? null,
  };
}

/**
 * Process a user message and advance the conversation state.
 * @param {object} session  - mutated in place
 * @param {string} message  - raw user input
 * @returns {object}        - { nextPrompt, completed, collectedData, error? }
 */
function handleUserMessage(session, message) {
  if (session.completed) {
    return { nextPrompt: null, completed: true, collectedData: session.collectedData };
  }

  const step = session.flow.steps[session.stepIndex];
  if (!step) {
    session.completed = true;
    return { nextPrompt: null, completed: true, collectedData: session.collectedData };
  }

  // Validate input if a validator is provided
  if (step.validate && !step.validate(message)) {
    return {
      nextPrompt: step.reprompt ?? step.prompt,
      completed: false,
      collectedData: session.collectedData,
      error: 'validation_failed',
    };
  }

  // Store field value
  if (step.field) {
    const value = step.transform ? step.transform(message) : message.trim();
    session.collectedData[step.field] = value;
  }

  // Advance to next step
  session.stepIndex += 1;
  const nextStep = session.flow.steps[session.stepIndex];

  if (!nextStep || nextStep.terminal) {
    session.completed = true;
    return {
      nextPrompt: nextStep?.prompt ?? buildSummary(session),
      completed: true,
      collectedData: session.collectedData,
    };
  }

  // Support conditional prompts
  const nextPrompt =
    typeof nextStep.prompt === 'function'
      ? nextStep.prompt(session.collectedData)
      : nextStep.prompt;

  session.prompt = nextPrompt;

  return {
    nextPrompt,
    completed: false,
    collectedData: session.collectedData,
  };
}

/**
 * Auto-generate a simple confirmation summary.
 */
function buildSummary(session) {
  const lines = Object.entries(session.collectedData)
    .map(([k, v]) => `${k}: ${v}`)
    .join('\n');
  return `Спасибо! Я записал:\n${lines}\n\nМы свяжемся с вами в ближайшее время. До свидания!`;
}

module.exports = { startConversation, handleUserMessage };
