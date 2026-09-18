import rawConfig from './config.json'
import rawEvents from './events.json'

export type AgentStatus = 'idle' | 'working' | 'waiting' | 'completed' | 'blocked' | 'failed'
export type AgentEventType = 'task' | 'result' | 'status'

export interface AgentConfig {
  id: string
  name: string
  role: string
  visualId: string
  spotId: string
  color: string
  emoji: string
  initialStatus: AgentStatus
  displayLabel: string
}

export interface AgentSimulationConfig {
  version: number
  numberOfAgents: number
  managerAgentId: string
  defaultChannel: string
  agents: AgentConfig[]
  allowedConnections: [string, string][]
  statusLabels: Record<AgentStatus, string>
}

export interface AgentSimulationEvent {
  run_id: string
  from_agent: string
  to_agent: string
  type: AgentEventType
  message: string
  status: AgentStatus
  timestamp: string
}

export interface AgentVisualEvent {
  type: 'agent_message'
  fromAgent: string
  toAgent: string
  status: AgentStatus
  text: string
}

export interface ScheduledAgentEvent {
  event: AgentSimulationEvent
  delayMs: number
}

export const agentSimulationConfig = rawConfig as AgentSimulationConfig
export const mockAgentEvents = rawEvents as AgentSimulationEvent[]

export function getAgentConfig(agentId: string): AgentConfig | undefined {
  return agentSimulationConfig.agents.find(agent => agent.id === agentId)
}

export function isAllowedConnection(fromAgent: string, toAgent: string): boolean {
  return agentSimulationConfig.allowedConnections.some(
    ([from, to]) => from === fromAgent && to === toAgent,
  )
}

export function scheduleMockEvents(
  events: AgentSimulationEvent[] = mockAgentEvents,
  intervalMs = 9000,
): ScheduledAgentEvent[] {
  return [...events]
    .sort((left, right) => left.timestamp.localeCompare(right.timestamp))
    .filter(event => getAgentConfig(event.from_agent) && getAgentConfig(event.to_agent))
    .filter(event => isAllowedConnection(event.from_agent, event.to_agent))
    .map((event, index) => ({ event, delayMs: index * intervalMs }))
}

export function toAgentVisualEvent(event: AgentSimulationEvent): AgentVisualEvent | null {
  if (!getAgentConfig(event.from_agent) || !getAgentConfig(event.to_agent)) return null
  if (!isAllowedConnection(event.from_agent, event.to_agent)) return null

  return {
    type: 'agent_message',
    fromAgent: event.from_agent,
    toAgent: event.to_agent,
    status: event.status,
    text: event.message,
  }
}
