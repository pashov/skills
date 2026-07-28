// Dispatches the 12 attacker-specialty audit agents. Called by SKILL.md Turn 3a-W
// via Workflow({scriptPath: <this file>, args: {...}}). Claude Code only.
//
// args:
//   bundleDir             string  - the mktemp'd {bundle_dir} holding agent-N-bundle.md
//   agentModel            string  - "opus"|"sonnet"|"haiku" from Turn 1b, or null to
//                                   inherit the session model
//   bundles               array   - 12x {n:1..12, specialty:string, lines:number}
//                                   agents 1-9 get singleSpecialtyPrompt, 10-12 gapHunterPrompt
//   singleSpecialtyPrompt string  - Turn 3a-i template, {BUNDLE_PATH}/{LINES} left literal
//   gapHunterPrompt       string  - Turn 3a-ii template, same placeholders
//
// returns: {coverage:{total,ok,failed[]}, markers[], findings[], leads[]}
//   findings/leads are schema-validated and flattened, each tagged {agent, specialty}.
//   Turn 4 groups by group_key directly - never regex this output.

export const meta = {
  name: 'solidity-auditor-12',
  description: 'Run the 12 attacker-specialty audit agents over prebuilt bundles',
  phases: [{ title: 'Attack', detail: '12 specialty agents, one bundle each' }],
}

const input = typeof args === 'string' ? JSON.parse(args) : args
const { bundleDir, agentModel, bundles, singleSpecialtyPrompt, gapHunterPrompt } = input

const S = { type: 'string' }
const AUDIT_SCHEMA = {
  type: 'object',
  required: ['markers', 'findings', 'leads'],
  properties: {
    markers: {
      type: 'object',
      required: ['feynman', 'socratic', 'inversion'],
      properties: {
        feynman: { type: 'number' },
        socratic: { type: 'number' },
        inversion: { type: 'number' },
        transcript: S,
      },
    },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        required: ['contract', 'function', 'bug_class', 'group_key', 'path', 'proof', 'description', 'fix'],
        properties: {
          contract: S, function: S, bug_class: S, group_key: S,
          path: S, proof: S, description: S, fix: S,
        },
      },
    },
    leads: {
      type: 'array',
      items: {
        type: 'object',
        required: ['contract', 'function', 'bug_class', 'group_key', 'code_smells', 'description'],
        properties: {
          contract: S, function: S, bug_class: S, group_key: S,
          code_smells: S, description: S,
        },
      },
    },
  },
}

phase('Attack')

const results = await parallel(bundles.map((b) => () => {
  const template = b.n <= 9 ? singleSpecialtyPrompt : gapHunterPrompt
  const prompt = template
    .split('{BUNDLE_PATH}').join(bundleDir + '/agent-' + b.n + '-bundle.md')
    .split('{LINES}').join(String(b.lines))
  const opts = {
    label: 'agent-' + b.n + ':' + b.specialty,
    phase: 'Attack',
    schema: AUDIT_SCHEMA,
  }
  if (agentModel) opts.model = agentModel
  return agent(prompt, opts).then((r) =>
    r ? { ok: true, ...b, ...r } : { ok: false, ...b, error: 'agent returned null' })
}))

const settled = results.map((r, i) => r || { ok: false, ...bundles[i], error: 'agent threw or was skipped' })
const ok = settled.filter((r) => r.ok)

return {
  coverage: {
    total: bundles.length,
    ok: ok.length,
    failed: settled.filter((r) => !r.ok).map((r) => r.n + ':' + r.specialty + ' (' + r.error + ')'),
  },
  markers: ok.map((r) => ({ agent: r.n, specialty: r.specialty, ...r.markers })),
  findings: ok.flatMap((r) => (r.findings || []).map((f) => ({ agent: r.n, specialty: r.specialty, ...f }))),
  leads: ok.flatMap((r) => (r.leads || []).map((l) => ({ agent: r.n, specialty: r.specialty, ...l }))),
}
