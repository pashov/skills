// Step 9d: the 2 property implementers in parallel, sharing one working tree.
// Called via Workflow({scriptPath: <this file>, args: {...}}). Claude Code only.
//
// args:
//   agentModel   string - resolved {AGENT_MODEL}
//   implementers array  - 2x {label:string, prompt:string}, labels
//                         "global-property-implementer" / "specific-property-implementer"
//
// Do NOT add isolation:'worktree' - the specific implementer wires handlers against
// ghosts the global one adds, and both edit PROPERTIES.md. Step 9e's build catches
// any collision.

export const meta = {
  name: 'fizz-property-implementers',
  description: 'Implement global and specific properties into the fuzz harness in parallel',
  phases: [{ title: 'Implement', detail: 'global + specific property implementers' }],
}

const input = typeof args === 'string' ? JSON.parse(args) : args
const { agentModel, implementers } = input

phase('Implement')
const results = await parallel(implementers.map((i) => () =>
  agent(i.prompt, { label: i.label, phase: 'Implement', model: agentModel })))

return results
  .map((r, i) => '### ' + implementers[i].label + '\n\n' + (r || '(agent returned nothing)'))
  .join('\n\n---\n\n')
