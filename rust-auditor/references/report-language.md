# Report language — Simplified Technical English

Every sentence a human reads in the report obeys this file. The rules are ASD-STE100
(Simplified Technical English), reduced to the part an audit finding needs.

## Why

A report is read by the developer who must fix the code, often at speed, often not in their
first language. A sentence they must decode twice costs the fix, and the bug stays in the
code. The scan is only as good as the sentence that delivers it.

Short words do not make a finding less rigorous. The proof is the diff in the **Fix** block
and the location on the meta line. The sentence exists to say what breaks and who breaks it.

## What this covers

Four pieces of text, and no others:

- the finding **title**
- the **Description** sentence
- the **Lead** description
- the **code smells** list on a Lead

## What it must never touch

These are data, not prose. Rewriting one of them for readability breaks the scan:

- **Rust identifiers** — program, module, instruction, function, struct, field and account
  names, and seed literals. They are printed as the source spells them. `withdraw_to_treasury`
  is never softened to `withdraw to treasury`, and `b"vault"` stays `b"vault"`.
- **The diff inside a Fix block.** It is code. It is pasted verbatim from the agent that wrote
  it, and `judging.md` and `dedup-and-assembly.md` both forbid paraphrase there.
- **The bug-class label** (`missing-owner-check`). It is the third segment of a memory key.
  The same bug under a plainer word is a second ledger record, so memory remembers it twice
  and recognises it never. Labels are chosen by the rules in `dedup-and-assembly.md` step 1,
  never by this file.
- **Fixed strings the assembler prints** — the banner, the Scope table headers, the italic
  lines under Leads and "Known from earlier scans", the disclaimer. They are in
  `assemble.sh` and they are already written.

## The rules

1. **One sentence, one idea.** A Description is one sentence. Two fixed sentences from
   `judging.md` do not count toward it and go at the end: `Stubbed: impact as named.` (Gate 4)
   and the masking sentence that starts `This path works after` (Gate 1). A Lead description is
   one or two. Never three.
2. **Twenty-five words is the ceiling.** Count them. Over the ceiling means two ideas in one
   sentence — cut it or split it.
3. **Active voice, and name the actor.** Who does this? Write that word first.
   - No: `Funds can be drained due to a missing signer check.`
   - Yes: `Any caller can take all the tokens, because the instruction does not require the authority to sign.`
4. **Simple present tense.** The code does this today. Not `would be able to`, not
   `could potentially`. If the path is uncertain it is a Lead, and the Lead says which step
   is unproven.
5. **No `-ing` clauses.** They hide the actor and the order of events. Use `that`, `so`, or a
   second sentence.
   - No: `Missing owner check allowing anyone to substitute the config.`
   - Yes: `The instruction does not check the owner of the config account, so any caller can pass a fake config.`
6. **Keep the articles.** `the`, `a`, `an`. Telegraphic style — `Function reverts on zero
   amount` — is not shorter to read, only shorter to type.
7. **Three nouns in a row is the limit.** Break a longer stack with `of`, `for` or `in`.
   - No: `vault token account authority validation gap`
   - Yes: `the instruction does not check the authority of the vault token account`
8. **One word for one thing, every time.** Pick `token`, or pick `asset`, and use that word
   in the title, the Description and the fix. A synonym reads as a second thing. The same holds
   for `instruction` (not `function` in one sentence and `endpoint` in the next) and for
   `account`.
9. **No metaphor, no idiom, no slang.** See the table below. A metaphor is a word the reader
   must translate before they can act.
10. **Say what happens, not how bad it is.** `catastrophic`, `critical`, `severe` and
    `trivially` carry no information — the confidence number and the Fix block carry it. Write
    the effect: `the caller keeps the tokens and the pool keeps the debt`.
11. **Positive statements. No double negatives.** `The check is absent` beats `the check is
    not present`.
12. **Event order is sentence order.** Cause, then effect. `The price comes from the pool
    balance, so an attacker who moves the balance moves the price.`
13. **A title is one clause, twelve words or fewer,** present tense, active, and it names the
    defect or its effect. `Withdraw accepts any token account as the vault.`
    Not `Account validation vulnerability in withdraw functionality`.

## Words to replace

Left column: the wording to keep out of the report. Right column: what the report prints.

| Do not write | Write |
| --- | --- |
| burns the funds (when no SPL `burn` happens) | sends the tokens to an account that nobody can spend from |
| bricks the program / bricks the account | makes the instruction fail for every caller, forever |
| rug / rugpull | the admin takes the user deposits |
| account cosplay / type cosplay | passes an account of a different type |
| spoofs the account | passes a fake account |
| drains | takes all the tokens / all the lamports |
| revives the account | sends lamports back to the closed account, so it stays alive |
| griefing | an attacker makes the instruction fail for other users |
| footgun | (delete the word and name the defect) |
| silently swallows the error | ignores the error |
| DoS / denial of service | blocks every caller |
| attack surface / attack vector | path |
| malicious actor / bad actor | an attacker |
| leverages / utilizes | uses |
| is able to | can |
| in order to | to |
| arbitrary value | any value the caller chooses |
| stale price | old price |
| sanity check | check |
| happy path | the normal path |
| atomically | in one transaction |
| permissionless crank | an instruction that any caller can send |
| trustlessly / permissionlessly | (delete, or name who may call) |
| non-zero | more than zero |
| cascading failures | (name each failure) |
| exponentially / trivially / catastrophically | (delete) |
| edge case | (name the input or the state) |

## Technical names stay

STE-100 keeps technical names, and a security report cannot work without them:
`signer`, `owner`, `PDA`, `seeds`, `bump`, `discriminator`, `CPI`, `lamports`, `rent`,
`realloc`, `sysvar`, `mint`, `token account`, `ATA`, `delegate`, `slippage`, `oracle`,
`overflow`, `rounding`, `slot`. Use them. They are precise and the reader who fixes a Solana
program knows them.

The rule is what goes **around** them: name the mechanism once with its technical name, then
say in plain words what the attacker gets.

- No: `Classic stale-account bug enabling double-counting after CPI.`
- Yes: `The instruction reads the vault balance before the CPI and uses it after, so the
  attacker gets shares for tokens the vault did not receive.`

## Worked examples

Before, and after. The code the sentence describes did not change.

**One**

- Before: `Improper validation of the destination account results in a catastrophic loss of
  user funds via account cosplay.`
- After: `The instruction accepts any token account as the vault, so an attacker passes their
  own account and receives the withdrawal.`

**Two**

- Before: `Lack of slippage protection in the swap path exposes users to sandwich attacks,
  potentially leading to significant value extraction by MEV searchers.`
- After: `The swap instruction takes no minimum output, so an attacker who trades before and
  after the victim keeps most of the output.`

**Three — a Lead**

- Before: `Potential accounting inconsistency stemming from Token-2022 transfer fee handling
  on deposit/withdraw flows warranting further investigation.`
- After: `The deposit records the amount sent, and the vault receives the amount minus the
  transfer fee. We did not prove that a mint with a fee can reach this vault.`

## Self-check before you write the block

Four questions. Any `no` means rewrite the sentence, not the code:

- Does the sentence name **who** acts and **what** they get?
- Is it one sentence, twenty-five words or fewer, with no `-ing` clause?
- Is every word in it a word the reader does not have to translate?
- Are the identifiers, the label and the diff exactly as the source and the agent wrote them?
