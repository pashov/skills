// Path B fact extraction: one reader per source subsystem, plus the Step 1 spec-doc
// reader. Called via Workflow({scriptPath: <this file>, args: {...}}). Claude Code only.
// Only used when 2+ readers apply; a lone reader goes through the Agent tool instead.
//
// args:
//   readers array - {label:string, prompt:string}; label is the subsystem name,
//                   or "spec-docs" for the Step 1 doc reader
//
// Readers are pinned to sonnet: they extract facts, they do not analyze.

export const meta = {
  name: 'xray-path-b-readers',
  description: 'Read source subsystems and spec docs in parallel, returning structured fact extractions',
  phases: [{ title: 'Read', detail: 'one reader per subsystem / doc set' }],
}

const input = typeof args === 'string' ? JSON.parse(args) : args
const { readers } = input

phase('Read')
const out = await parallel(readers.map((r) => () =>
  agent(r.prompt, { label: r.label, phase: 'Read', model: 'sonnet' })))

return out
  .map((r, i) => '### READER — ' + readers[i].label + '\n\n' + (r || '(reader returned nothing)'))
  .join('\n\n---\n\n')
