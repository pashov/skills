# Report Formatting

## Disclaimer

Open the report with this disclaimer block, verbatim:

> ⚠️ This review was performed by an AI assistant. AI analysis can never verify the complete absence of vulnerabilities and no guarantee of security is given. Team security reviews, bug bounty programs, and on-chain monitoring are strongly recommended.

---

## Severity Classification

| Severity | Emoji | Criteria |
|---|---|---|
| **CRITICAL** | ⛔ | Direct theft or permanent loss/freeze of user or protocol funds; full protocol takeover; governance capture that gives an attacker unilateral control. |
| **HIGH** | 🔴 | Significant financial loss through realistic attack paths; temporary freeze of user funds; theft of unclaimed yield or rewards; loss of core protocol functionality. |
| **MEDIUM** | 🟡 | Limited or conditional financial impact requiring specific preconditions; DoS or griefing that causes disruption without direct profit; protocol misbehavior under edge conditions. |
| **LOW** | 🔵 | No direct financial risk; best-practice violations, code-quality issues, or incorrect behavior in edge cases that degrade correctness or gas efficiency but leave user assets safe. |

Do not report INFO findings.

---

## Output Format

```
# 🔐 Security Review — <ContractName or repo name>

> ⚠️ This review was performed by an AI assistant. AI analysis can never verify the complete absence of vulnerabilities and no guarantee of security is given. Team security reviews, bug bounty programs, and on-chain monitoring are strongly recommended.

---

## Findings

| # | | Severity | Title |
|---|---|---|---|
| 1 | 🟠 | HIGH | <title> |
| 2 | 🟡 | MEDIUM | <title> |
| 3 | 🔵 | LOW | <title> |

---

<severity emoji> **1. [HIGH, N] <Title>**

**Location** `ContractName.functionName` · line N
**Description** <vector name — what is wrong and why it matters — what an attacker can do>
**Mitigation** <concrete recommendation using text and inline code references, no fenced code blocks>

---

<severity emoji> **2. [MEDIUM, N] <Title>**
...

---

## Scope

| | |
|---|---|
| **Mode** | ALL / default / filename |
| **Files reviewed** | `File1.sol` · `File2.sol`<br>`File3.sol` · `File4.sol` |
| **Confidence threshold** | N |
| **Below threshold** | N |
```

**Rules:**

- Title the report with a lock emoji and the repo or contract name.
- Order findings Critical first, then High, Medium, Low in both the table and the detail sections.
- Number findings sequentially; the number in the table matches the heading number.
- Each severity level in the table gets its emoji. Each finding heading is preceded by its severity emoji on the same line.
- Omit severity levels that have no findings.
- Confidence score goes inside the severity brackets: `[HIGH, 91]`, `[MEDIUM, 78]`, etc.
- Separate each finding with `---`.
- Do not use fenced code blocks in Mitigation. Use prose with inline `code` references.
- The disclaimer is always printed, even when there are no findings.
- Scope is a two-column table, not a prose paragraph.
