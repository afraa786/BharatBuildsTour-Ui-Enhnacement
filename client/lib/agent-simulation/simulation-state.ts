import type { AgentStatus, AgentSimulationConfig, AgentSimulationEvent } from './simulation'

export interface SimulationState {
  statusByAgent: Record<string, AgentStatus>
  activeAgentId: string | null
  lastEvent: AgentSimulationEvent | null
  conversation: AgentSimulationEvent[]
}

export function createInitialSimulationState(config: AgentSimulationConfig): SimulationState {
  return {
    statusByAgent: Object.fromEntries(config.agents.map(agent => [agent.id, agent.initialStatus])),
    activeAgentId: null,
    lastEvent: null,
    conversation: [],
  }
}

export function reduceSimulationState(
  state: SimulationState,
  event: AgentSimulationEvent,
): SimulationState {
  if (!state.statusByAgent[event.from_agent] || !state.statusByAgent[event.to_agent]) return state

  return {
    statusByAgent: {
      ...state.statusByAgent,
      [event.from_agent]: 'working',
      [event.to_agent]: event.status,
    },
    activeAgentId: event.to_agent,
    lastEvent: event,
    conversation: [...state.conversation.slice(-49), event],
  }
}
