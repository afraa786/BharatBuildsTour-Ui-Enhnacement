StockAware Agent Visualization JSON Specification

1. Agent Visual Configuration

File: config.json

{
  "id": "inventory",
  "name": "Inventory",
  "role": "inventory-agent",
  "visualId": "employee-1",
  "spotId": "spot-3",
  "color": "#38bdf8",
  "emoji": "📦",
  "initialStatus": "idle",
  "displayLabel": "Stock Desk"
}

Supported statuses

"idle"
"working"
"waiting"
"completed"
"blocked"
"failed"

spotId

spotId must match an existing desk/spot in the office, such as:

"spot-1"
"spot-2"
"spot-3"
"spot-4"
"spot-5"
"spot-6"
"spot-7"

visualId

visualId identifies the sprite/character used for the agent. Example values:

"Me-1"
"Claude-1"
"employee-1"
"employee-2"
"employee-3"
"Frontend-dev-1"
"security-audit-1"

2. Mock Agent Event Format

File: events.json

Mock events simulate messages and status changes that will later come from the real agent backend.

{
  "run_id": "RFQ-1042",
  "from_agent": "manager",
  "to_agent": "inventory",
  "type": "task",
  "message": "Check stock for 20 16A switches.",
  "status": "working",
  "timestamp": "2026-09-18T09:00:00.000Z"
}

Supported event types

"task"
"result"
"status"

Result event example

{
  "run_id": "RFQ-1042",
  "from_agent": "inventory",
  "to_agent": "manager",
  "type": "result",
  "message": "Stock check complete. Two items are below threshold.",
  "status": "blocked",
  "timestamp": "2026-09-18T09:00:06.000Z"
}

3. Agent Connections

The from_agent and to_agent values in events.json must match agent IDs defined in config.json.

The same communication pair must also be listed in allowedConnections.

Example:

"allowedConnections": [
  ["manager", "inventory"],
  ["inventory", "manager"]
]

This defines the allowed communication paths between agents.

4. Expected Visualization Behavior

The visual system should automatically:

Find agents defined in config.json.

Use their configured visualId for the character/sprite.

Place them at the configured spotId.

Initialize them with initialStatus.

Read events.json sequentially.

Validate from_agent and to_agent against configured agents.

Validate communication against allowedConnections.

Update agent status from each event.

Activate/highlight the sender.

Activate/highlight the recipient.

Show the event message in the existing chat UI.

Display the message as the recipient speech bubble where applicable.

Animate communication using the existing visualization.

Update the simulation/timeline state.

Preserve the current visual design and interactions.

5. Configuration-Driven Requirement

The visualization code must not hardcode:

Agent count

Agent names

Agent IDs

Agent roles

Agent colors

Agent emojis

Agent desk positions

Agent sprite IDs

Initial statuses

Agent communication pairs

Changing config.json must be enough to:

Add an agent

Remove an agent

Rename an agent

Change an agent role

Change an agent sprite

Move an agent to another desk

Change an agent's initial status

Changing events.json must be enough to change the simulated conversation and workflow.

No visualization component should require code changes when agents are renamed, added, removed, or reordered.

6. Mock-to-Backend Integration Seam

For now:

config.json
    ↓
events.json
    ↓
Simulation State
    ↓
Existing Agent Visualization

Later, replace only the mock event source:

Real Backend / WebSocket / Event Stream
    ↓
Simulation State
    ↓
Existing Agent Visualization

The visualization layer should remain unchanged when switching from mock events to real agent events.