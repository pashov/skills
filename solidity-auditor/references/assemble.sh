#!/usr/bin/env bash
# THE ASSEMBLER. It writes the whole solidity-auditor report. SKILL.md Turn 5 runs it.
#
# This is the only producer of a report in this skill. The orchestrator does not compose one,
# and must not be re-taught to: an orchestrator under context pressure is the thing that
# failed. Every finding this scan gated is in a run file; this script prints all of them or
# says out loud that it could not.
#
#   assemble.sh --dir .solidity-auditor/runs/{stamp}
#
# Reads ONE directory and writes {dir}/full-report.md — the complete report, banner line down
# to the disclaimer, ready to print word for word. No model judgment runs in here.
#
# reads   dir/run-K.md          the run files (ticket 01 shape), one per pass, model-written
#         dir/scope.tsv         key <TAB> value, append-only, LAST LINE PER KEY WINS
#         dir/memory-before.tsv the pruned photocopy — its PRESENCE is not the memory flag,
#                               scope.tsv's `mem_before` key is
#         dir/source-names.tsv  normalised <TAB> as spelled in the source
# writes  dir/full-report.md
#
# The model types the markers, so it can mistype one. The assembler CHECKS them and prints
# the disagreement into the Scope table. A broken run file becomes a visible line in the
# report, never a silent loss.
#
# Written to .part and moved into place on exit 0, so a half-report never exists.
set -euo pipefail

dir=
while [ $# -gt 0 ]; do
  case "$1" in
    --dir) dir=$2; shift 2 ;;
    *) echo "assemble.sh: unknown argument $1" >&2; exit 2 ;;
  esac
done
[ -d "$dir" ] || { echo "assemble.sh: no such directory $dir" >&2; exit 2; }

out="$dir/full-report.md"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

THRESHOLD=75   # judging.md sets it. Named there and read here; never a second opinion.

# ---------------------------------------------------------------- scope.tsv, last wins
# An absent key gives an absent row. That is what keeps a plain scan's table at four rows.
# A missing scope.tsv is every key missing at once — the same path, no special case. It must
# not be a non-zero exit either: `set -e` would turn one absent label into no report at all.
scope() {
  [ -f "$dir/scope.tsv" ] || return 0
  awk -F'\t' -v k="$1" '$1==k { v=$2 } END { print v }' "$dir/scope.tsv"
}

name=$(scope name);            [ -n "$name" ] || name='**name missing**'
mode=$(scope mode);            [ -n "$mode" ] || mode='**Mode missing**'
passes_planned=$(scope passes_planned)
mem_before=$(scope mem_before)
mem_after=$(scope mem_after)
mem_sha=$(scope mem_sha)

memory_on=0; [ -n "$mem_before" ] && memory_on=1
if [ "$memory_on" = 1 ] && [ ! -f "$dir/memory-before.tsv" ]; then
  echo "assemble.sh: memory is on but $dir/memory-before.tsv is missing — Turn 5 did not copy it" >&2
  memory_on=0
fi

# run files in PASS order. A plain glob puts run-10 before run-2, which is a real 10-pass bug.
runs=()
while IFS= read -r f; do runs+=("$f"); done < <(
  ls "$dir"/run-*.md 2>/dev/null | sed 's/.*run-\([0-9]*\)\.md/\1 &/' | sort -n | cut -d' ' -f2)
N=${#runs[@]}

# ---------------------------------------------------------------- index every block
# key conf kind agents file pass start end bodystart bodyend title loc leadbody
#
# A FINDING and a LEAD are NOT the same shape on disk, and one geometry read over both is what
# produced `- **- **Title**` rows and a "Body missing" line under leads that had a body:
#
#   FINDING            LEAD
#   +0  <!--F ...-->   +0  <!--F ...-->
#   +1                 +1
#   +2  [95] **1. T**  +2  - **T** — `loc` · TAG — smells — why not verified
#   +3                 +3
#   +4  `loc` · Conf   +4  <!--/F-->
#   +5
#   +6  body …
#
# Read with the finding geometry, a lead put its WHOLE formatted line in `title` (which the
# emitter then wrapped in `- **…**` a second time), found no backticks at +4 so `loc` came out
# empty, and had no body region at all. Each kind now gets its own reader.
#
# **No field is ever emitted empty** — `-` stands in. `read` below splits on IFS=$'\t', and a
# tab is IFS *whitespace*, so bash collapses `\t\t` into one delimiter and every later field
# shifts left by one. That is how a lead's memory tag ended up printed as its location.
: > "$work/index.tsv"
for f in ${runs[@]+"${runs[@]}"}; do
  awk -v F="$f" '
    /^<!--RUN / { line=$0; sub(/[[:space:]]*-->[[:space:]]*$/, "", line)
                  n=split(line, a, /[[:space:]]+/)
                  for (i=2; i<=n; i++) { eq=index(a[i],"="); if (substr(a[i],1,eq-1)=="pass") pass=substr(a[i],eq+1) } }
    /^<!--F / {
      key=""; conf=""; kind=""; agents=""
      line = $0
      sub(/[[:space:]]*-->[[:space:]]*$/, "", line)   # terminator off BEFORE splitting
      n = split(line, a, /[[:space:]]+/)
      for (i = 2; i <= n; i++) {
        eq = index(a[i], "="); nm = substr(a[i], 1, eq-1); v = substr(a[i], eq+1)
        if (nm == "key") key = v; else if (nm == "conf") conf = v
        else if (nm == "kind") kind = v; else if (nm == "agents") agents = v
      }
      if (conf == "") conf = "-"        # a LEAD is not scored
      start = NR; title = ""; loc = ""; lbody = ""
      next
    }
    kind != "LEAD" && start && NR == start + 2 { t = $0; sub(/^\[[0-9]+\] /, "", t); sub(/^\*\*/, "", t); sub(/\*\*$/, "", t); title = t }
    kind != "LEAD" && start && NR == start + 4 { l = $0; if (match(l, /`[^`]*`/)) loc = substr(l, RSTART+1, RLENGTH-2) }

    # A lead is one line. Split it here, once, so the emitter formats leads and findings with
    # the same fields instead of re-printing a line that is already formatted.
    # `match` + RSTART/RLENGTH, never index()+a literal width: the separator is an em dash,
    # 3 bytes and 1 character, and the two disagree across awks and locales.
    kind == "LEAD" && start && NR == start + 2 && /^- \*\*/ {
      l = $0
      sub(/^- \*\*/, "", l)
      if (match(l, /\*\* — /)) { title = substr(l, 1, RSTART-1); l = substr(l, RSTART+RLENGTH) }
      else                     { title = l; l = "" }
      if (match(l, /^`[^`]*`/)) { loc = substr(l, RSTART+1, RLENGTH-2); l = substr(l, RSTART+RLENGTH) }
      # What is left is " · NEW — body" or " — body". Either way the body starts after the
      # first " — ". The inline tag is DROPPED: the assembler derives the memory tag itself
      # from memory-before.tsv, and two sources for one fact is how they come to disagree.
      if (match(l, / — /)) l = substr(l, RSTART+RLENGTH); else l = ""
      lbody = l
    }
    /^<!--\/F-->/ && start {
      if (title == "") title = "-"
      if (loc   == "") loc   = "-"
      if (lbody == "") lbody = "-"
      print key "\t" conf "\t" kind "\t" agents "\t" F "\t" pass "\t" start "\t" NR "\t" (start+6) "\t" (NR-1) "\t" title "\t" loc "\t" lbody
      start = 0; kind = ""
    }
  ' "$f" >> "$work/index.tsv"
done

# ---------------------------------------------------------------- the structure check
# The model typed these markers. When the counts disagree, a finding was raised and cannot be
# read — say so IN the report. The report may print less than the scan found; it may never
# claim to print more.
#
# No run file at all is the same rule at its limit: pass 1 produced nothing, so the scan
# reviewed nothing. That is a REPORT, not an exit — SKILL.md Turn 3b routes a real scan down
# here, and a shell error in place of a report is the one outcome this skill must never have.
# The row is necessary because the Passes row is suppressed on a 1-pass scan, so without it
# nothing in the report would say the pass died.
broken=
if [ "$N" = 0 ]; then
  broken="⚠️ No pass produced a run file. This scan reviewed nothing."
  echo "assemble.sh: NO RUN FILES — $broken" >&2
else
  opens=$(cat "${runs[@]}" | grep -c '^<!--F ' || :)
  closes=$(cat "${runs[@]}" | grep -c '^<!--/F-->' || :)
  indexed=$(wc -l < "$work/index.tsv" | tr -d ' ')
  if [ "$opens" != "$closes" ] || [ "$opens" != "$indexed" ]; then
    broken="⚠️ $opens findings marked, $indexed readable. $(( opens - indexed )) could not be read and are missing below. See the run files."
    echo "assemble.sh: STRUCTURE BROKEN — $broken" >&2
  fi
fi

# ---------------------------------------------------------------- dedup across runs
# One winner per key: strongest kind, then highest confidence, then the LATER pass — a later
# pass read the ledger every earlier pass wrote, so it is the better-informed write-up.
# k counts every run that raised the key, in either section.
sort -t $'\t' -k1,1 "$work/index.tsv" | awk -F'\t' '
  function rank(k) { return (k == "FINDING") ? 1 : 0 }
  {
    if (!(($5 SUBSEP $1) in seenrun)) { seenrun[$5 SUBSEP $1]=1; k[$1]++ }
    c = ($2 == "-") ? -1 : $2 + 0
    if (!($1 in best) || rank($3) > br[$1] || (rank($3) == br[$1] && c > bc[$1]) \
        || (rank($3) == br[$1] && c == bc[$1] && $6 + 0 >= bp[$1])) {
      best[$1] = $0; br[$1] = rank($3); bc[$1] = c; bp[$1] = $6 + 0
    }
  }
  END { for (key in best) print k[key] "\t" best[key] }
' > "$work/merged.tsv"

# ---------------------------------------------------------------- the memory tag
# Derived here from memory-before.tsv, not carried in the marker. One source: the report and
# the ledger cannot disagree because both read the same photocopy.
#   KNOWN (n scans) — the STORED count plus one; this scan has just found it again.
if [ "$memory_on" = 1 ]; then
  awk -F'\t' -v OFS='\t' '
    FILENAME==ARGV[1] { if (FNR>1) sc[$1]=$3; next }
    { print $0, ($2 in sc) ? "KNOWN (" sc[$2]+1 " scans)" : "NEW" }
  ' "$dir/memory-before.tsv" "$work/merged.tsv" > "$work/merged.tagged.tsv"
else
  awk -F'\t' -v OFS='\t' '{ print $0, "" }' "$work/merged.tsv" > "$work/merged.tagged.tsv"
fi

# columns now: 1 k · 2 key · 3 conf · 4 kind · 5 agents · 6 file · 7 pass · 8 start · 9 end
#              10 bodystart · 11 bodyend · 12 title · 13 loc · 14 leadbody · 15 memtag
# 12, 13 and 14 are never empty — `-` stands in, because IFS=$'\t' collapses adjacent tabs.
sort -t $'\t' -k4,4 -k3,3nr -k2,2 "$work/merged.tagged.tsv" > "$work/sorted.tsv"
awk -F'\t' '$4=="FINDING"' "$work/sorted.tsv" > "$work/findings.tsv"
awk -F'\t' '$4=="LEAD"'    "$work/sorted.tsv" > "$work/leads.tsv"

nfind=$(wc -l < "$work/findings.tsv" | tr -d ' ')
nlead=$(wc -l < "$work/leads.tsv" | tr -d ' ')

# ---------------------------------------------------------------- emit
R="$work/report.md"
: > "$R"
say() { printf '%s\n' "$1" >> "$R"; }
rule() { say ""; say "---"; say ""; }
row() { printf '| %s | %s |\n' "$1" "$2" >> "$R"; }

say "# 🔐 Security Review — $name"
rule
say "## Scope"
say ""
row "" ""
row "---" "---"
row "**Mode**" "$mode"

# Files reviewed — 3 per line, in source.md order, joined with `<br>`. One `files` key holds
# them space separated; shell does the wrapping.
files=$(scope files | tr ' ' '\n' | awk 'NF { printf "`%s`", $0; if (++n % 3 == 0) printf "<br>"; else printf " · " }' \
        | sed -e 's/ · $//' -e 's/<br>$//')
row "**Files reviewed**" "$files"
row "**Confidence threshold (1-100)**" "$THRESHOLD"

# The Passes cell is COMPOSED from facts, never written as prose by a model.
if [ -n "$passes_planned" ] && [ "$passes_planned" -gt 1 ] 2>/dev/null; then
  short=""
  for k in $(seq 1 "$passes_planned"); do
    a=$(scope "pass_${k}_agents"); fail=$(scope "pass_${k}_failed")
    if [ -n "$fail" ]; then short="${short:+$short, }pass $k failed"
    elif [ -n "$a" ] && [ "$a" != "12/12" ]; then short="${short:+$short, }pass $k ran $a agents"; fi
  done
  if [ "$N" -lt "$passes_planned" ]; then cell="$N of $passes_planned"; else cell="$passes_planned"; fi
  [ -n "$short" ] && cell="$cell ($short)"
  row "**Passes**" "$cell"
fi
[ "$memory_on" = 1 ] && row "**Memory**" "$mem_before records before this scan · $mem_after after · \`$mem_sha\`"
[ -n "$broken" ] && row "**Run files**" "$broken"
rule

say "## Findings"
say ""

emit_body() {  # file bodystart bodyend  — copied through, never re-worded
  awk -v s="$2" -v e="$3" 'NR>=s && NR<=e' "$1" \
    | awk '{ lines[++n] = $0 } END {
        b=1; while (b<=n && lines[b]=="") b++
        while (n>=b && lines[n]=="") n--
        for (i=b; i<=n; i++) print lines[i] }'
}

i=0
while IFS=$'\t' read -r k key conf kind agents file pass start end bstart bend title loc lbody memtag; do
  i=$((i+1))
  [ "$title" = "-" ] && title="**Title missing** — the block's title line could not be read"
  if [ "$loc" = "-" ]; then meta="**location missing**"; else meta="\`$loc\`"; fi
  say "[$conf] **$i. $title**"
  say ""
  meta="$meta · Confidence: $conf"
  [ "$N" -gt 1 ] && meta="$meta · seen in $k/$N runs"
  [ -n "$memtag" ] && meta="$meta · $memtag"
  say "$meta"
  say ""
  body=$(emit_body "$file" "$bstart" "$bend")
  if [ -z "$body" ]; then
    say "**Body missing** — pass $pass raised this finding and wrote no description."
  else
    printf '%s\n' "$body" >> "$R"
  fi
  rule
done < "$work/findings.tsv"

if [ "$nfind" = 0 ]; then
  # An empty table with a header row and no rows under it is not a report of nothing, it is a
  # report that looks broken. Say it in words instead.
  say "_None — this scan raised no findings._"
  rule
else
say "Findings List"
say ""
say "| # | Confidence | Title |"
say "|---|---|---|"
i=0; sep=0
while IFS=$'\t' read -r k key conf kind agents file pass start end bstart bend title loc lbody memtag; do
  i=$((i+1))
  if [ "$sep" = 0 ] && [ "$conf" -lt "$THRESHOLD" ]; then
    say "| | | **Below Confidence Threshold** |"; sep=1
  fi
  say "| $i | [$conf] | $title |"
done < "$work/findings.tsv"
rule
fi

say "## Leads"
say ""
say "_Vulnerability trails with concrete code smells where the full exploit path could not be completed in one analysis pass. These are not false positives — they are high-signal leads for manual review. Not scored._"
say ""
[ "$nlead" = 0 ] && say "_None._"
while IFS=$'\t' read -r k key conf kind agents file pass start end bstart bend title loc lbody memtag; do
  seg=""
  [ "$N" -gt 1 ] && seg="$seg · seen in $k/$N runs"
  [ -n "$memtag" ] && seg="$seg · $memtag"
  # The body was parsed out of the lead's own line by the indexer. Do NOT read it back out of
  # the run file here: a lead has no body region, so emit_body returned nothing and every lead
  # got the "Body missing" line whether or not it had one.
  [ "$title" = "-" ] && title="**Title missing** — the lead's line could not be read"
  if [ "$loc" = "-" ]; then locmd="**location missing**"; else locmd="\`$loc\`"; fi
  [ "$lbody" = "-" ] && lbody="**Body missing** — pass $pass raised this lead and wrote no description."
  say "- **$title** — $locmd$seg — $lbody"
done < "$work/leads.tsv"

# ---------------------------------------------------------------- Known from earlier scans
# The keys this scan raised come from the index — the run files are the record, so no separate
# run-keys.tsv or scan-rows.tsv has to be carried in.
if [ "$memory_on" = 1 ]; then
  held=$(( $(wc -l < "$dir/memory-before.tsv") - 1 ))
  if [ "$held" -gt 0 ]; then
    tail -n +2 "$dir/memory-before.tsv" | cut -f1 | sort -u > "$work/keys-before.txt"
    cut -f1 "$work/index.tsv" | sort -u > "$work/keys-scan.txt"
    comm -23 "$work/keys-before.txt" "$work/keys-scan.txt" > "$work/keys-left.txt"
    rule
    say "## Known from earlier scans"
    say ""
    say "_Recorded by earlier scans of this repo, not raised again by this one. Not re-checked — a record here may be fixed, or may still be live and missed. \`.solidity-auditor/memory.tsv\`._"
    say ""
    if [ -s "$work/keys-left.txt" ]; then
      say "| Scans | Kind | Location | Title |"
      say "|---|---|---|---|"
      awk -F'\t' '
        FILENAME==ARGV[1] { nm[$1]=$2; next }
        FILENAME==ARGV[2] { if (FNR>1) { sc[$1]=$3; ti[$1]=$5; ki[$1]=$6 } ; next }
        {
          split($1, p, "|")
          c = (p[1] in nm) ? nm[p[1]] : p[1]      # print-as-stored when the segment is not in the map
          f = (p[2] in nm) ? nm[p[2]] : p[2]
          print "| " sc[$1] " | " ki[$1] " | `" c "." f "` | " ti[$1] " |"
        }
      ' "$dir/source-names.tsv" "$dir/memory-before.tsv" "$work/keys-left.txt" >> "$R"
    else
      say "_None — every record in the ledger was raised again by this scan._"
    fi
  fi
fi

rule
say "> ⚠️ This review was performed by an AI assistant. AI analysis can never verify the complete absence of vulnerabilities and no guarantee of security is given. Team security reviews, bug bounty programs, and on-chain monitoring are strongly recommended. For a consultation regarding your projects' security, visit [https://www.pashov.com](https://www.pashov.com)"

cp "$R" "$out.part"
mv "$out.part" "$out"
echo "assembled $out — $nfind findings, $nlead leads, $N run files"
