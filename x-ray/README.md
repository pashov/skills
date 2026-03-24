# X-Ray

Built for:

- **Protocol teams** — stay aware of your threat model and security gaps throughout development and before audits
- **Security researchers** — get the full picture in minutes on new audit start

Not a vulnerability scanner — it's the briefing you read before opening the first file. One command produces:

| Output             | What's Inside                                                                          |
| ------------------ | -------------------------------------------------------------------------------------- |
| `x-ray.md`         | Protocol overview, threat model, invariants, test gaps, git history, readiness verdict |
| `entry-points.md`  | Every state-changing function classified by access level with call chains              |
| `architecture.svg` | Visual architecture diagram — contracts, actors, trust boundaries                      |

## Demo

_Part of an X-Ray report generation shown below_

![Running x-ray in terminal](../static/x_ray.gif)

## Usage

```
Install latest https://github.com/pashov/skills/ and run x-ray on the codebase
```

## Tips

- **Start with the verdict.** The report ends with a tier (FORTIFIED → EXPOSED) and 3-5 action items. If you only read one section, read that.
- **Use entry-points.md as your map.** Start with permissionless functions — those are the highest-risk surface.
- **Check the action items.** The final section highlights concrete next steps — whether you're preparing for an audit or starting one.
