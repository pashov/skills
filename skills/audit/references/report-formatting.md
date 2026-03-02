# Report Formatting

## Report Path

Save the report to `assets/findings/{project-name}-pashov-ai-audit-report-{timestamp}.md` where `{project-name}` is the repo root basename and `{timestamp}` is `YYYYMMDD-HHMMSS` at scan time.

## Output Format

````
# 🔐 Security Review — <ContractName or repo name>

> ⚠️ This review was performed by an AI assistant. AI analysis can never verify the complete absence of vulnerabilities and no guarantee of security is given. Team security reviews, bug bounty programs, and on-chain monitoring are strongly recommended. For a consultation regarding your projects' security, visit [https://www.pashov.com](https://www.pashov.com)

---

## Scope

|                                  |                                                        |
| -------------------------------- | ------------------------------------------------------ |
| **Mode**                         | ALL / default / filename                               |
| **Files reviewed**               | `File1.sol` · `File2.sol`<br>`File3.sol` · `File4.sol` | <!-- list every file, 3 per line -->
| **Confidence threshold (1-100)** | N                                                      |

---

## Findings

| # | Confidence | Title |
|---|---|---|
| 1 | 🔴 95 | <title> |
| 2 | 🟡 82 | <title> |
| | | **Below Confidence Threshold** |
| 3 | 🟡 75 | <title> |
| 4 | 🔵 60 | <title> |

---

🔴 **1. <Title>**

`ContractName.functionName` · Confidence: 95

**Description**
<The vulnerable code pattern and why it is exploitable, in 1 short sentence>

**Fix**

```diff
- vulnerable line(s)
+ fixed line(s)
````

---

🟡 **2. <Title>**
...

```

**Rules:**

- Title the report with a lock emoji and the repo or contract name.
- Order findings by confidence score, highest first, in both the table and the detail sections.
- Number findings sequentially; the number in the table matches the heading number.
- The Confidence column combines the indicator and score (e.g., `🔴 95`). Indicators: 🔴 > 90, 🟡 75–90, 🔵 < 75. Each finding heading is preceded by its indicator.
- Location and Confidence appear as a single inline line below the heading: `` `Contract.fn` · Confidence: N ``.
- Description and Fix are each a bold label on its own line followed by the content on the next line.
- Separate each finding with `---`.
- Findings below the confidence threshold are listed in the table and get a detail section with description only — no **Fix** block. Draw a separator row `| **Below Confidence Threshold** |` between the last above-threshold finding and the first below-threshold finding.
- **Timing:** Draft findings directly in report format — the terminal output IS the report content. After every 3 findings, print a timestamp. After all findings, write the complete report to the file in a single Write call. Do not re-generate findings.
```
