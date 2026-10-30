async function resolvePrompt(step, session) {
  if (typeof step.prompt === 'function') {
    return step.prompt(session);
  }

  return step.prompt ?? null;
}

function resolveNextIndex(step, session, userMessage, toolResult) {
  if (toolResult && toolResult.nextStepId) {
    return session.flow.findIndex((candidate) => candidate.id === toolResult.nextStepId);
  }

  if (typeof step.next === 'function') {
    const computed = step.next(userMessage, session.collected, session, toolResult);

    if (typeof computed === 'number') {
      return computed;
    }

    if (typeof computed === 'string') {
      return session.flow.findIndex((candidate) => candidate.id === computed);
    }
  }

  if (typeof step.next === 'number') {
    return step.next;
  }

  if (typeof step.next === 'string') {
    return session.flow.findIndex((candidate) => candidate.id === step.next);
  }

  if (step.next === null) {
    return session.flow.length;
  }

  return session.index + 1;
}

async function runAutoSteps(session) {
  while (session.index < session.flow.length) {
    const step = session.flow[session.index];
    if (!step.autoRun) {
      session.prompt = await resolvePrompt(step, session);
      if (step.terminal) {
        session.index = session.flow.length;
      }
      return;
    }

    let toolResult = null;
    if (step.tool) {
      toolResult = await step.tool(session.lastUserMessage || '', session.collected, session);
      session.toolCalls.push({
        stepId: step.id,
        toolName: step.tool.name || step.id,
        result: toolResult,
      });
      session.lastToolResult = toolResult;
    }

    const autoPrompt = await resolvePrompt(step, session);
    if (autoPrompt) {
      session.systemMessages.push(autoPrompt);
    }

    const nextIndex = resolveNextIndex(step, session, session.lastUserMessage || '', toolResult);
    if (nextIndex < 0 || nextIndex >= session.flow.length) {
      session.index = session.flow.length;
      session.prompt = autoPrompt || null;
      return;
    }

    session.index = nextIndex;
  }

  session.prompt = null;
}

async function startConversation(flow) {
  const session = {
    flow,
    index: 0,
    collected: {},
    toolCalls: [],
    systemMessages: [],
    lastToolResult: null,
    lastUserMessage: null,
    prompt: null,
  };

  await runAutoSteps(session);
  return session;
}

async function handleUserMessage(session, userMessage) {
  if (session.index >= session.flow.length) {
    return {
      prompt: null,
      completed: true,
      collectedData: session.collected,
      toolCalls: session.toolCalls,
      systemMessages: [],
    };
  }

  session.systemMessages = [];
  session.lastUserMessage = userMessage.trim();

  const currentStep = session.flow[session.index];

  if (currentStep.field) {
    session.collected[currentStep.field] = session.lastUserMessage;
  }

  let toolResult = null;
  if (currentStep.tool) {
    toolResult = await currentStep.tool(session.lastUserMessage, session.collected, session);
    session.toolCalls.push({
      stepId: currentStep.id,
      toolName: currentStep.tool.name || currentStep.id,
      result: toolResult,
    });
    session.lastToolResult = toolResult;
  }

  const nextIndex = resolveNextIndex(currentStep, session, session.lastUserMessage, toolResult);
  if (nextIndex < 0 || nextIndex >= session.flow.length) {
    session.index = session.flow.length;
    session.prompt = null;
  } else {
    session.index = nextIndex;
    await runAutoSteps(session);
  }

  return {
    prompt: session.prompt,
    completed: session.index >= session.flow.length,
    collectedData: session.collected,
    toolCalls: session.toolCalls,
    systemMessages: session.systemMessages,
  };
}

module.exports = {
  handleUserMessage,
  startConversation,
};
