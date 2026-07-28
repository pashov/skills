// Steps 9b+9c: 5 invariant-discovery agents in parallel, then the Synthesizer.
// Called via Workflow({scriptPath: <this file>, args: {...}}). Claude Code only.
//
// args:
//   agentModel  string - resolved {AGENT_MODEL} ("sonnet" default, "opus" with --max)
//   discovery   array  - 5x {label:string, prompt:string} fully substituted
//   synthesizer string - Synthesizer prompt, {AGENT_OUTPUTS} left as a literal placeholder
//
// returns: {discovery: string, plan: string}
//   The guided-mode PROPERTIES.md review happens in the parent agent after this
//   returns - workflows take no mid-run user input.

export const meta = {
  name: 'fizz-invariant-discovery',
  description: 'Run 5 invariant-discovery agents in parallel, then synthesize the property plan',
  phases: [
    { title: 'Discover', detail: '5 discovery agents, one lens each' },
    { title: 'Synthesize', detail: 'merge, dedupe, prioritize, write PROPERTIES.md' },
  ],
}

const input = typeof args === 'string' ? JSON.parse(args) : args
const { agentModel, discovery, synthesizer } = input

phase('Discover')
const found = await parallel(discovery.map((d) => () =>
  agent(d.prompt, { label: d.label, phase: 'Discover', model: agentModel })))

const outputs = found
  .map((r, i) => '### ' + discovery[i].label + '\n\n' + (r || '(agent returned nothing)'))
  .join('\n\n---\n\n')

phase('Synthesize')
const plan = await agent(
  synthesizer.split('{AGENT_OUTPUTS}').join(outputs),
  { label: 'synthesizer', phase: 'Synthesize', model: agentModel },
)

return { discovery: outputs, plan }
