---
name: unluac-debug
description: Reproduce and locate decompilation semantic errors, readability gaps, or HIR/AST pass proof issues in unluac-rs, and produce the smallest Lua regression and verification results. Suitable for failed cases, erroneous generated source, inlining, or lifetime issues; does not trigger for ordinary documentation, build configuration, or release tasks.
---

# unluac Diagnosis and Repair

The goal is to explain the source of the first deviation and, upon user request, complete the corresponding modification and verification. Read-only audits deliver findings with evidence; a fix for one case does not automatically expand into a full pass or full-repo audit.

## Entry and Evidence

- Project conventions are found in [AGENTS.md](../../../AGENTS.md). Reuse existing source cases, manifest variants, and debugging capabilities first; do not create a separate runner or parallel pass for the same input shape.
- Determine the source or chunk, dialect, options, and observed difference from the failure conditions provided by the user. Expand to corresponding debug modes only when dealing with naming or debug identities; do not change a stripped problem to a debug-preserved one and claim a fix.
- Commands are found in the [Debug Manual](../../../docs/debug.md), and owner navigation is in the [Maintenance Map](../../../docs/design.md). Select the dump from the earliest possible layer that could be erroneous, and use proto and pass filters to narrow output; do not traverse all stages every time.

The following examples are run from the repository root; replace case, dialect, and pass with current reproduction conditions:

```powershell
cargo unluac -s tests/case_calls/roots_01_non_tail_callable_root.lua -D lua5.4 --dump-pass temp-inline,inline-exprs --detail verbose
cargo case-test --case-filter non_tail_callable_root --output verbose
```

The first command is for observing the generation process, and the second is for the test chain of compilation, run-comparison, and assertions. When in doubt about parameter parsing or default values, check the current CLI / runner; do not replace run-equivalence evidence with a single successful generation or old disk artifacts.

## Selecting the Repair Location

- Compare input, stage products, and before/after results of related passes to confirm the first deviation in fact loss, erroneous consumption, or candidate rewrite. Repair in the natural owner of the fact and reuse its existing analysis and queries.
- Home, root lifetime, and protocol facts of the original VM are proven before or within the HIR; AST proofs verify the legality of candidate Lua source rewrites. Read [HIR](../../../docs/design/5.hir.md) and [AST readability](../../../docs/design/7.readability.md) as needed, and do not reverse-infer physical root survival from the AST call site.
- When deleting, moving, or merging expressions, prove the evaluation count and order, value snapshots, multi-return width, metamethods, and lifetimes involved in the candidate. For weak references or GC, use the smallest probe that can observe differences for the affected dialect; results from one VM cannot be extrapolated as cross-dialect proof.
- Record rejection reasons and acceptance proofs according to the [Pass guard contract](../../../docs/design.md#pass-guard-合同). If equivalence cannot be proven, preserve the original shape and indicate the missing fact; when a concrete non-equivalence counter-example is found, fix or tighten the acceptance path, and do not use shorter source as a reason for loosening.

## Verification and Completion

- Fixes use the smallest compilable Lua source regression, registered in the corresponding module routed by `packages/unluac-test-support/src/case_manifest.rs`; prioritize extending cases or variants of the same theme. For display contracts, add `unluac:` assertions, while run-comparisons must still be retained.
- Complete targeted verification and delivery checks according to the [Test System](../../../docs/design/11.test.md#Verification-by-modification). Record the actual execution scope, differences, and unverified conditions; if unable to reproduce, state the evidence gap honestly instead of writing speculation as a root cause.
- Only perform a full call chain check of candidates, helpers, rejection exits, and submission points when the user explicitly requests a pass audit; retrieval tags are for navigation only. Deliver after completing the requested scope, without chasing irrelevant guards.
