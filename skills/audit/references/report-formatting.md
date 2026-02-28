# Report Formatting

## Disclaimer

Open the report with this disclaimer block, verbatim:

> ⚠️ This review was performed by an AI assistant. AI analysis can never verify the complete absence of vulnerabilities and no guarantee of security is given. For a consultation regarding your projects' security, visit [https://www.pashov.com](https://www.pashov.com)

---

## Severity Classification

| Severity     | Emoji | Criteria                                                                                                                                                                            |
| ------------ | ----- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **CRITICAL** | ⛔    | Direct theft or permanent loss/freeze of user or protocol funds; full protocol takeover; governance capture that gives an attacker unilateral control.                              |
| **HIGH**     | 🔴    | Significant financial loss through realistic attack paths; temporary freeze of user funds; theft of unclaimed yield or rewards; loss of core protocol functionality.                |
| **MEDIUM**   | 🟡    | Limited or conditional financial impact requiring specific preconditions; DoS or griefing that causes disruption without direct profit; protocol misbehavior under edge conditions. |
| **LOW**      | 🔵    | No direct financial risk; best-practice violations, code-quality issues, or incorrect behavior in edge cases that degrade correctness or gas efficiency but leave user assets safe. |

When uncertain between two severity levels, always assign the lower one. CRITICAL and HIGH require a complete, end-to-end exploit path with meaningful value at risk and no significant preconditions — not theoretical or role-gated scenarios. Most findings are MEDIUM or LOW.

Do not report INFO findings.

---

## Output Format

````
# 🔐 Security Review — <ContractName or repo name>

> ⚠️ This review was performed by an AI assistant. AI analysis can never verify the complete absence of vulnerabilities and no guarantee of security is given. Team security reviews, bug bounty programs, and on-chain monitoring are strongly recommended. For security consulting, contact www.pashov.com

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

| | |
|---|---|
| **Location** | `ContractName.functionName` · line N |
| **Confidence** | N |

**Impact**
<Full sentence explaining what an attacker concretely achieves: who is affected, what they lose or gain, and what the worst-case outcome is — e.g. "An attacker can drain all ETH held by the contract in a single transaction, causing permanent loss of user funds with no recovery path.">

**Description**
<The vulnerable code pattern and why it is exploitable, in 1–2 sentences.>

**Fix**
<Concrete code change that resolves the vulnerability. Show exactly what to change as a diff:>

```diff
- vulnerable line(s)
+ fixed line(s)
````

<One sentence confirming the attack path no longer succeeds with this fix applied.>

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
- Location and Confidence are rendered as a two-column table immediately below the finding heading. Confidence is not included in the severity brackets.
- Impact, Description, and Fix are each a bold label on its own line followed by the content on the next line, with a blank line separating each section.
- Separate each finding with `---`.
- Fix must include a fenced diff code block showing the exact lines to change, followed by one sentence confirming the fix eliminates the attack path.
- The disclaimer is always printed, even when there are no findings.
- Scope is a two-column table immediately after the disclaimer, not a prose paragraph.
- The "Confidence threshold" label always reads `Confidence threshold (1-100)`.
- Suppressed findings appear at the end of the report as a `## Suppressed Findings` section rendered as a three-column table (`Confidence · Location · Description`), not as prose. One row per suppressed finding. Descriptions are one sentence: what the issue is and why it was suppressed.
```
