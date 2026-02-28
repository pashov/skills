# Report Formatting

## Report Path

Save the report to `assets/findings/{project-name}-pashov-ai-audit-report-{timestamp}.md` where `{project-name}` is the repo root basename and `{timestamp}` is `YYYYMMDD-HHMMSS` at scan time.

## Severity Classification

| Severity     | Emoji | Criteria                                                                                                                                                                            |
| ------------ | ----- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **CRITICAL** | ⛔    | Direct theft or permanent loss/freeze of user or protocol funds; full protocol takeover; governance capture that gives an attacker unilateral control.                              |
| **HIGH**     | 🔴    | Significant financial loss through realistic attack paths; temporary freeze of user funds; theft of unclaimed yield or rewards; loss of core protocol functionality.                |
| **MEDIUM**   | 🟡    | Limited or conditional financial impact requiring specific preconditions; DoS or griefing that causes disruption without direct profit; protocol misbehavior under edge conditions. |
| **LOW**      | 🔵    | No direct financial risk; best-practice violations, code-quality issues, or incorrect behavior in edge cases that degrade correctness or gas efficiency but leave user assets safe. |

When uncertain between two severity levels, always assign the lower one. CRITICAL and HIGH require a complete, end-to-end exploit path with meaningful value at risk and no significant preconditions.

**Downgrade rules:**

- Privileged caller required (owner, admin, multisig, governance) → drop one level.
- Impact is self-contained (attacker's own funds only, unreachable state, narrow subset with no spillover) → drop one level.
- No direct monetary loss (disruption, griefing, gas waste, incorrect state) → cap at MEDIUM.
- Attack path is incomplete (cannot write caller → call sequence → concrete outcome) → drop one level.
- Uncertain between two levels → choose the lower.

CRITICAL and HIGH are rare. If you have more than one, re-examine each before returning.

**Do not report:** INFO-level findings, issues a linter or compiler would catch, or pedantic nitpicks a serious engineer would omit (gas micro-optimizations, naming preferences, missing NatSpec, redundant comments). If a finding would make a seasoned auditor roll their eyes, leave it out.

## Output Format

````
# 🔐 Security Review — <ContractName or repo name>

> ⚠️ This review was performed by an AI assistant. AI analysis can never verify the complete absence of vulnerabilities and no guarantee of security is given. Team security reviews, bug bounty programs, and on-chain monitoring are strongly recommended. For a consultation regarding your projects' security, visit [https://www.pashov.com](https://www.pashov.com)

---

## Scope

|                                  |                                                        |
| -------------------------------- | ------------------------------------------------------ |
| **Mode**                         | ALL / default / filename                               |
| **Files reviewed**               | `File1.sol` · `File2.sol`<br>`File3.sol` · `File4.sol` |
| **Confidence threshold (1-100)** | N                                                      |

---

## Findings

| # | | Severity | Title |
|---|---|---|---|
| 1 | 🟠 | HIGH | <title> |
| 2 | 🟡 | MEDIUM | <title> |
| 3 | 🔵 | LOW | <title> |

---

<severity emoji> **1. [HIGH] <Title>**

`ContractName.functionName` · line N · Confidence: N

**Description**
<The vulnerable code pattern and why it is exploitable, in 1–2 sentences.>

**Fix**

```diff
- vulnerable line(s)
+ fixed line(s)
````

---

<severity emoji> **2. [MEDIUM] <Title>**
...

---

## Suppressed Findings

| Confidence | Location            | Description                                                  |
| ---------- | ------------------- | ------------------------------------------------------------ |
| N          | `Contract.function` | One-sentence summary of the issue and why it was suppressed. |

```

**Rules:**

- Title the report with a lock emoji and the repo or contract name.
- Order findings Critical first, then High, Medium, Low in both the table and the detail sections.
- Number findings sequentially; the number in the table matches the heading number.
- Each severity level in the table gets its emoji. Each finding heading is preceded by its severity emoji on the same line.
- Omit severity levels that have no findings.
- Location and Confidence appear as a single inline line below the heading: `` `Contract.fn` · line N · Confidence: N ``.
- Description and Fix are each a bold label on its own line followed by the content on the next line.
- Separate each finding with `---`.
- Fix must include a fenced diff code block showing the exact lines to change.
- The disclaimer is always printed, even when there are no findings.
- The Summary section appears between Scope and Findings. It is 1–2 sentences: state the number and severity breakdown of findings, highlight the most critical risk areas, and recommend that the team address the findings and pursue a formal security review before deployment. Keep the tone professional and direct — no hedging, no filler.
- Scope is a two-column table immediately after the disclaimer, not a prose paragraph.
- The "Confidence threshold" label always reads `Confidence threshold (1-100)`.
- Suppressed findings appear at the end of the report as a `## Suppressed Findings` section rendered as a three-column table (`Confidence · Location · Description`), not as prose. One row per suppressed finding. Descriptions are one sentence: what the issue is and why it was suppressed.
- **Timing:** Print each finding to the terminal as you draft it. After every 3 findings (and after the last one), get a timestamp via `date +%H:%M:%S` and print `⏱ [HH:MM:SS] Findings 1-3 drafted` (adjusting the range). After all findings are drafted, write the complete report to the file in a single Write call.
```
