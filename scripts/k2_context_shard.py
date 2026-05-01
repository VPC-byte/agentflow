#!/usr/bin/env python3
"""Run a focused K2 Code4rena context-pack shard through OpenRouter."""

from __future__ import annotations

import argparse
import glob
import json
import os
from pathlib import Path
import sys
import time
from typing import Any
from urllib import error, request


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "moonshotai/kimi-k2.5"


GLOBAL_PATTERNS = [
    "README.md",
    "README_SPONSOR.md",
    "scope.txt",
    "out_of_scope.txt",
    "tests/README.md",
    "tests/c4/Cargo.toml",
    "tests/c4/src/lib.rs",
    "docs/00-INDEX.md",
    "docs/01-OVERVIEW.md",
    "docs/02-ARCHITECTURE.md",
    "docs/03-CORE-CONCEPTS.md",
    "docs/05-FLOWS.md",
    "docs/09-SECURITY.md",
]

COMPACT_GLOBAL_PATTERNS = [
    "README.md",
    "scope.txt",
    "out_of_scope.txt",
    "tests/c4/Cargo.toml",
    "tests/c4/src/lib.rs",
    "docs/00-INDEX.md",
]

V12_FILES = [
    "K2-V12-Critical-output.md",
    "K2-V12-High-output.md",
    "K2-V12-Med-Low-output.md",
]


SHARDS: dict[str, dict[str, Any]] = {
    "router_solvent_indices": {
        "target": "KineticRouter solvency accounting, scaled balances, interest indices, and aToken/debtToken consistency",
        "focus": (
            "Audit supply, withdraw, borrow, repay, update_state, reserve index updates, scaled "
            "balances, health-factor reads, collateral/debt bitmap interactions, and aToken/debtToken "
            "mint/burn paths. Prioritize direct bad debt, phantom collateral, stuck funds, or an "
            "unsafe account state reachable by an unprivileged user through public protocol calls. "
            "Do not report V12 TTL/archival issues, public known issues, or already-tested remediation cases."
        ),
        "patterns": [
            "docs/07-INTEREST-MODEL.md",
            "docs/10-STORAGE.md",
            "contracts/kinetic-router/src/router.rs",
            "contracts/kinetic-router/src/calculation.rs",
            "contracts/kinetic-router/src/storage.rs",
            "contracts/kinetic-router/src/operations.rs",
            "contracts/kinetic-router/src/reserve.rs",
            "contracts/kinetic-router/src/validation.rs",
            "contracts/kinetic-router/src/views.rs",
            "contracts/kinetic-router/src/price.rs",
            "contracts/kinetic-router/src/events.rs",
            "contracts/a-token/src/*.rs",
            "contracts/debt-token/src/*.rs",
            "contracts/shared/src/*.rs",
            "tests/unit-tests/src/kinetic_router_test.rs",
            "tests/unit-tests/src/kinetic_router_test_supply_borrow.rs",
            "tests/unit-tests/src/kinetic_router_test_health_factor_validation.rs",
            "tests/unit-tests/src/kinetic_router_test_invariants.rs",
            "tests/unit-tests/src/kinetic_router_test_large_numbers.rs",
            "tests/unit-tests/src/a_token_test.rs",
            "tests/unit-tests/src/debt_token_test.rs",
            "tests/integration-tests/src/test_lending_flow.rs",
            "tests/integration-tests/src/test_interest_accrual.rs",
            "tests/integration-tests/src/test_hf_state.rs",
        ],
    },
    "liquidation_hf_bad_debt": {
        "target": "Liquidation paths, health-factor validation, close factor, bonus, and bad-debt accounting",
        "focus": (
            "Audit regular liquidation_call plus liquidation-engine helpers for cases where liquidation "
            "does not improve solvency, creates or hides deficit, over-seizes collateral, lets debt remain "
            "uncollectable, or permits an invalid liquidator/borrower route. Exclude the public self-liquidation "
            "known issue and V12 findings such as exact-collateral deficit, worsening liquidation, and reserve-cap "
            "liquidation freezes unless you find a materially different root cause and impact."
        ),
        "patterns": [
            "docs/06-LIQUIDATION.md",
            "contracts/kinetic-router/src/liquidation.rs",
            "contracts/kinetic-router/src/calculation.rs",
            "contracts/kinetic-router/src/validation.rs",
            "contracts/kinetic-router/src/storage.rs",
            "contracts/kinetic-router/src/router.rs",
            "contracts/kinetic-router/src/operations.rs",
            "contracts/kinetic-router/src/price.rs",
            "contracts/liquidation-engine/src/*.rs",
            "contracts/a-token/src/*.rs",
            "contracts/debt-token/src/*.rs",
            "contracts/shared/src/*.rs",
            "tests/unit-tests/src/kinetic_router_test_liquidation.rs",
            "tests/unit-tests/src/kinetic_router_test_liquidation_whitelist.rs",
            "tests/unit-tests/src/liquidation_engine_test.rs",
            "tests/integration-tests/src/test_liquidation_flow.rs",
            "tests/integration-tests/src/test_liquidator.rs",
            "tests/integration-tests/src/test_hf_state.rs",
        ],
    },
    "oracle_circuit_breaker": {
        "target": "Price oracle cascade, manual overrides, custom oracles, Reflector fallback, cache TTL, and circuit breaker",
        "focus": (
            "Audit oracle priority order, stale-price handling, 20% circuit breaker behavior, decimal conversion, "
            "asset binding, batch price reads, manual override expiry, and router price consumption. Prioritize "
            "borrow/withdraw/liquidation paths that use an unsafe price, freeze the wrong price, or silently "
            "misvalue collateral/debt. Exclude V12 batch-price and stale-baseline findings unless materially new."
        ),
        "patterns": [
            "docs/08-ORACLE.md",
            "contracts/price-oracle/src/*.rs",
            "contracts/kinetic-router/src/price.rs",
            "contracts/kinetic-router/src/calculation.rs",
            "contracts/kinetic-router/src/validation.rs",
            "contracts/pool-configurator/src/oracle.rs",
            "contracts/pool-configurator/src/storage.rs",
            "contracts/shared/src/*.rs",
            "tests/unit-tests/src/price_oracle_test.rs",
            "tests/unit-tests/src/price_oracle_test_precision.rs",
            "tests/unit-tests/src/kinetic_router_test_price_calc.rs",
            "tests/integration-tests/src/test_oracle_integration.rs",
            "tests/integration-tests/src/test_redstone_integration.rs",
        ],
    },
    "flashloan_flashliquidation": {
        "target": "Flash loan and two-step flash liquidation atomicity, premiums, callbacks, and swap-handler assumptions",
        "focus": (
            "Audit flash_loan, execute_operation callback trust, premium rounding, repayment checks, "
            "prepare_liquidation/execute_liquidation state machine, liquidation helper validation, and DEX-backed "
            "repayment flows. Exclude the public memory-budget issue for two-step flash liquidation at 2+ reserves."
        ),
        "patterns": [
            "docs/06-LIQUIDATION.md",
            "docs/08-DEX-INTEGRATION.md",
            "contracts/kinetic-router/src/flash_loan.rs",
            "contracts/kinetic-router/src/liquidation.rs",
            "contracts/kinetic-router/src/swap.rs",
            "contracts/kinetic-router/src/storage.rs",
            "contracts/kinetic-router/src/router.rs",
            "contracts/flash-liquidation-helper/src/*.rs",
            "contracts/aquarius-swap-adapter/src/lib.rs",
            "contracts/soroswap-swap-adapter/src/lib.rs",
            "contracts/shared/src/*.rs",
            "tests/unit-tests/src/kinetic_router_test_flash_loan.rs",
            "tests/unit-tests/src/kinetic_router_test_execute_operation_security.rs",
            "tests/unit-tests/src/flash_liquidation_helper_test.rs",
            "tests/integration-tests/src/test_flash_loan.rs",
            "tests/integration-tests/src/test_flash_loan_dex_integration.rs",
            "tests/integration-tests/src/test_flash_liquidation.rs",
            "tests/integration-tests/src/test_prepare_execute_liquidation.rs",
        ],
    },
    "bitmap_reserve_reindexing": {
        "target": "Reserve id allocation, bitmap bounds, reserve drop/re-register, ACL, whitelist, blacklist, and 64-reserve edge cases",
        "focus": (
            "Audit NEXT_RESERVE_ID, RESERVE_ID mappings, user configuration bits, reserve activation/drop/re-register, "
            "ACL/whitelist/blacklist scans, 64-reserve limit behavior, and stale/removal collisions. Avoid V12 TTL-expiry "
            "and first-64 ACL findings unless the candidate is a distinct live public-call issue."
        ),
        "patterns": [
            "docs/10-STORAGE.md",
            "docs/11-ADMIN.md",
            "contracts/kinetic-router/src/storage.rs",
            "contracts/kinetic-router/src/reserve.rs",
            "contracts/kinetic-router/src/router.rs",
            "contracts/kinetic-router/src/admin.rs",
            "contracts/kinetic-router/src/access_control.rs",
            "contracts/kinetic-router/src/validation.rs",
            "contracts/pool-configurator/src/reserve.rs",
            "contracts/pool-configurator/src/contract.rs",
            "contracts/pool-configurator/src/storage.rs",
            "contracts/shared/src/*.rs",
            "tests/unit-tests/src/kinetic_router_reserve_id_collision_poc.rs",
            "tests/unit-tests/src/kinetic_router_test_reserve_id_fix.rs",
            "tests/unit-tests/src/kinetic_router_test_blacklist.rs",
            "tests/unit-tests/src/kinetic_router_test_blacklist_bypass.rs",
            "tests/integration-tests/src/test_reserve_fragmentation.rs",
        ],
    },
    "dex_adapters_slippage_auth": {
        "target": "DEX adapter integration, swap-handler whitelist, slippage bounds, asset routing, and callback authorization",
        "focus": (
            "Audit Aquarius/Soroswap adapters, router swap execution, min-output enforcement, asset ordering, pool "
            "registration, swap-handler trust, forged pair data, and liquidation/flash-loan integrations. Exclude "
            "general DEX liquidity-depth/risk-parameter issues and V12 unverified-DEX-data duplicates."
        ),
        "patterns": [
            "docs/08-DEX-INTEGRATION.md",
            "contracts/shared/src/dex.rs",
            "contracts/aquarius-swap-adapter/src/lib.rs",
            "contracts/soroswap-swap-adapter/src/lib.rs",
            "contracts/kinetic-router/src/swap.rs",
            "contracts/kinetic-router/src/liquidation.rs",
            "contracts/kinetic-router/src/flash_loan.rs",
            "contracts/kinetic-router/src/storage.rs",
            "contracts/shared/src/*.rs",
            "tests/integration-tests/src/test_aquarius_integration.rs",
            "tests/integration-tests/src/test_k2_aquarius_full_integration.rs",
            "tests/integration-tests/src/test_swap_collateral.rs",
            "tests/integration-tests/src/test_flash_loan_dex_integration.rs",
        ],
    },
    "auth_pause_upgrade_roles": {
        "target": "Authentication, role separation, pause/unpause, initialization, and upgrade authority",
        "focus": (
            "Audit require_auth coverage, admin role separation, emergency pause semantics, upgrade authorization, "
            "initializer capture, treasury/admin paths, and repay-on-behalf authorization. Exclude pure trusted-admin "
            "misbehavior and V12 public-initializer/emergency-unpause findings unless a distinct untrusted path exists."
        ),
        "patterns": [
            "docs/09-SECURITY.md",
            "docs/11-ADMIN.md",
            "contracts/kinetic-router/src/admin.rs",
            "contracts/kinetic-router/src/emergency.rs",
            "contracts/kinetic-router/src/access_control.rs",
            "contracts/kinetic-router/src/upgrade.rs",
            "contracts/kinetic-router/src/router.rs",
            "contracts/pool-configurator/src/*.rs",
            "contracts/price-oracle/src/upgrade.rs",
            "contracts/a-token/src/upgrade.rs",
            "contracts/debt-token/src/upgrade.rs",
            "contracts/treasury/src/*.rs",
            "contracts/shared/src/upgradeable.rs",
            "contracts/shared/src/errors.rs",
            "tests/unit-tests/src/kinetic_router_test_auth_edge.rs",
            "tests/unit-tests/src/kinetic_router_test_upgrade.rs",
            "tests/integration-tests/src/test_auth.rs",
            "tests/integration-tests/src/test_upgrades.rs",
            "tests/integration-tests/src/test_treasury.rs",
        ],
    },
    "caps_debt_ceilings_rounding": {
        "target": "Supply caps, borrow caps, debt ceilings, min remaining debt, decimals, U256 math, and rounding boundaries",
        "focus": (
            "Audit cap enforcement under interest accrual, decimals conversion, U256-to-u128/i128 boundaries, "
            "round-up/down choices, minimum remaining debt, reserve factor fees, treasury accrual, and cross-asset "
            "precision. Prioritize public sequences that bypass caps, mint unbacked value, lose debt, or break solvency."
        ),
        "patterns": [
            "docs/04-COMPONENTS.md",
            "docs/07-INTEREST-MODEL.md",
            "contracts/kinetic-router/src/calculation.rs",
            "contracts/kinetic-router/src/validation.rs",
            "contracts/kinetic-router/src/params.rs",
            "contracts/kinetic-router/src/reserve.rs",
            "contracts/kinetic-router/src/treasury.rs",
            "contracts/interest-rate-strategy/src/*.rs",
            "contracts/treasury/src/*.rs",
            "contracts/shared/src/utils.rs",
            "contracts/shared/src/constants.rs",
            "contracts/shared/src/types.rs",
            "tests/unit-tests/src/kinetic_router_test_large_numbers.rs",
            "tests/unit-tests/src/kinetic_router_test_dynamic_precision.rs",
            "tests/unit-tests/src/kinetic_router_test_safety.rs",
            "tests/unit-tests/src/interest_rate_strategy_test.rs",
            "tests/integration-tests/src/test_interest_accrual.rs",
            "tests/integration-tests/src/test_critical_flows.rs",
        ],
    },
    "incentives_rewards": {
        "target": "Incentives reward accrual, claim flows, token hooks, emissions, funding, and reward-index lifecycle",
        "focus": (
            "Audit IncentivesContract, aToken/debtToken incentive hooks, router incentive wiring, reward-index "
            "updates, claim_rewards/claim_all_rewards, distribution end, emission changes, reward funding, "
            "paused/inactive rewards, and transfer/burn/mint edge cases. Prioritize public sequences that let "
            "users overclaim, underpay other users, permanently strand funded rewards, corrupt reward indexes, "
            "or bypass configured reward timing. Exclude V12/public duplicates around public initializer capture, "
            "stale manual claims, wrong supply query type, stale reward indexes/snapshots, emission rewrite, "
            "post-exit settlement, zero-total-supply lost rewards, and TTL-desynced registries unless the root "
            "cause and impact are materially different."
        ),
        "patterns": [
            "docs/04-COMPONENTS.md",
            "docs/05-FLOWS.md",
            "docs/09-SECURITY.md",
            "contracts/incentives/src/*.rs",
            "contracts/a-token/src/contract.rs",
            "contracts/a-token/src/storage.rs",
            "contracts/a-token/src/types.rs",
            "contracts/debt-token/src/contract.rs",
            "contracts/debt-token/src/storage.rs",
            "contracts/debt-token/src/types.rs",
            "contracts/kinetic-router/src/router.rs",
            "contracts/kinetic-router/src/params.rs",
            "contracts/kinetic-router/src/storage.rs",
            "contracts/shared/src/*.rs",
            "tests/unit-tests/src/incentives_test.rs",
            "tests/unit-tests/src/a_token_test.rs",
            "tests/unit-tests/src/debt_token_test.rs",
            "tests/integration-tests/src/test_incentives.rs",
            "tests/integration-tests/src/test_lending_flow.rs",
            "tests/integration-tests/src/test_critical_flows.rs",
        ],
    },
    "liquidation_engine_history": {
        "target": "LiquidationEngine helper accounting, liquidation history, cumulative limits, and router handoff consistency",
        "focus": (
            "Audit LiquidationEngine execute_liquidation/calculate_liquidation, liquidation history storage, "
            "per-user liquidation IDs, cumulative liquidation tracking, router liquidation_call handoff, price reads, "
            "and helper/native-router divergence. Prioritize public sequences that block valid liquidations, create "
            "stale or unbounded state with concrete protocol impact, miscalculate collateral/debt amounts versus the "
            "router, or record successful liquidation state when the underlying router call did not safely execute. "
            "Exclude V12/public duplicates including worsening liquidations, close-factor dust clamping, exact-collateral "
            "bad debt, public initializer capture, helper gas/resource-only observations without live liquidation impact, "
            "and broad unbounded-history claims unless you can show a runnable public path that breaks a High/Medium flow."
        ),
        "patterns": [
            "docs/06-LIQUIDATION.md",
            "docs/09-SECURITY.md",
            "contracts/liquidation-engine/src/*.rs",
            "contracts/kinetic-router/src/liquidation.rs",
            "contracts/kinetic-router/src/router.rs",
            "contracts/kinetic-router/src/calculation.rs",
            "contracts/kinetic-router/src/storage.rs",
            "contracts/kinetic-router/src/validation.rs",
            "contracts/kinetic-router/src/price.rs",
            "contracts/shared/src/*.rs",
            "tests/unit-tests/src/liquidation_engine_test.rs",
            "tests/unit-tests/src/kinetic_router_test_liquidation.rs",
            "tests/unit-tests/src/kinetic_router_test_liquidation_whitelist.rs",
            "tests/integration-tests/src/test_liquidation_flow.rs",
            "tests/integration-tests/src/test_liquidator.rs",
            "tests/integration-tests/src/test_hf_state.rs",
        ],
    },
    "treasury_deficit_accounting": {
        "target": "Treasury reserve collection, flash fees, bad-debt deficit tracking, and deficit cover accounting",
        "focus": (
            "Audit collect_protocol_reserves, cover_deficit, reserve deficit add/reduce paths, flash-loan premium "
            "transfers, liquidation bad-debt socialization, treasury contract withdrawals, and aToken/debtToken balance "
            "interactions. Prioritize public or authorized-user sequences that drain depositor liquidity, double-count "
            "fees/reserves, under-cover or over-clear deficits, strand funds, bypass deficit protection, or desync reserve "
            "accounting. Exclude trusted-admin-only treasury policy choices, V12 bad-debt/liquidation duplicates, and "
            "pure reporting/UI mismatches unless a concrete on-chain fund movement or solvency invariant breaks."
        ),
        "patterns": [
            "docs/04-COMPONENTS.md",
            "docs/06-LIQUIDATION.md",
            "docs/07-INTEREST-MODEL.md",
            "docs/10-STORAGE.md",
            "contracts/kinetic-router/src/treasury.rs",
            "contracts/kinetic-router/src/flash_loan.rs",
            "contracts/kinetic-router/src/liquidation.rs",
            "contracts/kinetic-router/src/router.rs",
            "contracts/kinetic-router/src/storage.rs",
            "contracts/kinetic-router/src/calculation.rs",
            "contracts/treasury/src/*.rs",
            "contracts/a-token/src/*.rs",
            "contracts/debt-token/src/*.rs",
            "contracts/shared/src/*.rs",
            "tests/unit-tests/src/treasury_test.rs",
            "tests/unit-tests/src/kinetic_router_test_treasury.rs",
            "tests/unit-tests/src/kinetic_router_test_flash_loan.rs",
            "tests/integration-tests/src/test_treasury.rs",
            "tests/integration-tests/src/test_flash_loan.rs",
            "tests/integration-tests/src/test_liquidation_flow.rs",
        ],
    },
    "cross_contract_auth_fallbacks": {
        "target": "Cross-contract invocation auth, fallback-to-zero/false handling, and token/router callback trust boundaries",
        "focus": (
            "Audit env.invoke_contract/try_invoke_contract call sites, require_auth boundaries, silent fallback handling, "
            "token hook calls, router self-auth assumptions, callback params, and conversion of cross-contract errors into "
            "zero/false values. Prioritize sequences where an untrusted contract or failed dependency causes unauthorized "
            "state changes, skipped accounting, minted/burned token desync, or successful user operations under failed "
            "security checks. Exclude V12 duplicates such as missing router self-auth, wrong scaled_total_supply type, "
            "public initializer capture, and trusted-admin-only dependency misconfiguration unless the root cause and "
            "impact are materially distinct."
        ),
        "patterns": [
            "docs/03-CORE-CONCEPTS.md",
            "docs/05-FLOWS.md",
            "docs/09-SECURITY.md",
            "contracts/kinetic-router/src/*.rs",
            "contracts/a-token/src/*.rs",
            "contracts/debt-token/src/*.rs",
            "contracts/incentives/src/*.rs",
            "contracts/liquidation-engine/src/*.rs",
            "contracts/treasury/src/*.rs",
            "contracts/shared/src/*.rs",
            "tests/unit-tests/src/kinetic_router_test_execute_operation_security.rs",
            "tests/unit-tests/src/kinetic_router_test_auth_edge.rs",
            "tests/unit-tests/src/a_token_test.rs",
            "tests/unit-tests/src/debt_token_test.rs",
            "tests/unit-tests/src/incentives_test.rs",
            "tests/integration-tests/src/test_auth.rs",
            "tests/integration-tests/src/test_flash_loan.rs",
        ],
    },
    "dex_asset_binding_precision": {
        "target": "DEX adapter asset binding, pair/factory assumptions, quote precision, and router swap integration",
        "focus": (
            "Audit Aquarius and Soroswap adapter token-index selection, pair/factory trust, swap output measurement, "
            "asset ordering, quote precision/overflow, direct-pair fallback, router swap handler configuration, and "
            "liquidation swap paths. Prioritize public sequences that swap the wrong assets, accept forged pool metadata, "
            "mis-measure output, bypass oracle-based slippage, or cause direct value loss in liquidation/flash-liquidation "
            "flows. Exclude generic DEX liquidity risk, trusted-admin whitelisting choices, and V12/public duplicate "
            "families around unverified DEX data unless you can demonstrate a distinct in-scope adapter bug."
        ),
        "patterns": [
            "docs/08-DEX-INTEGRATION.md",
            "contracts/shared/src/dex.rs",
            "contracts/aquarius-swap-adapter/src/lib.rs",
            "contracts/soroswap-swap-adapter/src/lib.rs",
            "contracts/kinetic-router/src/swap.rs",
            "contracts/kinetic-router/src/flash_loan.rs",
            "contracts/kinetic-router/src/liquidation.rs",
            "contracts/kinetic-router/src/router.rs",
            "contracts/kinetic-router/src/storage.rs",
            "contracts/shared/src/*.rs",
            "tests/integration-tests/src/test_aquarius_integration.rs",
            "tests/integration-tests/src/test_k2_aquarius_full_integration.rs",
            "tests/integration-tests/src/test_swap_collateral.rs",
            "tests/integration-tests/src/test_flash_loan_dex_integration.rs",
            "tests/unit-tests/src/audit_poc_pr78.rs",
        ],
    },
}


def read_text(path: Path, max_chars: int | None = None) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if max_chars is not None and len(text) > max_chars:
        return text[:max_chars] + f"\n\n[TRUNCATED after {max_chars} chars]\n"
    return text


def render_prompt(prompt: str, replacements: dict[str, str]) -> str:
    for key, value in replacements.items():
        prompt = prompt.replace("${" + key + "}", value)
    return prompt


def collect_context_files(
    repo: Path,
    patterns: list[str],
    per_file_limit: int,
    skip_aux_tests: bool,
) -> list[tuple[str, str]]:
    seen: set[Path] = set()
    files: list[tuple[str, str]] = []
    for pattern in patterns:
        matches = sorted(Path(p) for p in glob.glob(str(repo / pattern), recursive=True))
        for path in matches:
            if not path.is_file() or path in seen:
                continue
            seen.add(path)
            rel = path.relative_to(repo).as_posix()
            if skip_aux_tests and (
                rel.startswith("tests/unit-tests/") or rel.startswith("tests/integration-tests/")
            ):
                continue
            files.append((rel, read_text(path, per_file_limit)))
    return files


def extract_v12_manifest(repo: Path, max_chars: int) -> str:
    entries: list[str] = []
    for rel in V12_FILES:
        path = repo / rel
        if not path.exists():
            continue
        current_title: str | None = None
        current_id: str | None = None
        current_severity: str | None = None
        in_fence = False
        for line in read_text(path).splitlines():
            stripped = line.strip()
            if stripped.startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            if stripped.startswith("# ") and "Audited by" not in stripped:
                title = stripped[2:].strip()
                if title.lower() in {"install dependencies"}:
                    continue
                if current_title:
                    parts = [f"- {current_title}"]
                    if current_id:
                        parts.append(current_id)
                    if current_severity:
                        parts.append(current_severity)
                    entries.append(" ".join(parts))
                current_title = title
                current_id = None
                current_severity = None
            elif current_title and stripped.startswith("**#"):
                current_id = stripped.strip("*")
            elif current_title and stripped.startswith("- Severity:"):
                current_severity = stripped.removeprefix("- ").strip()
        if current_title:
            parts = [f"- {current_title}"]
            if current_id:
                parts.append(current_id)
            if current_severity:
                parts.append(current_severity)
            entries.append(" ".join(parts))
    manifest = "\n".join(entries)
    if len(manifest) > max_chars:
        return manifest[:max_chars] + f"\n\n[TRUNCATED V12 manifest after {max_chars} chars]\n"
    return manifest


def code_fence_language(rel: str) -> str:
    suffix = Path(rel).suffix
    if suffix == ".rs":
        return "rust"
    if suffix == ".toml":
        return "toml"
    if suffix == ".md":
        return "markdown"
    if suffix == ".txt":
        return "text"
    return ""


def build_user_prompt(
    *,
    shard_name: str,
    shard: dict[str, Any],
    contest_text: str,
    base_prompt: str,
    v12_manifest: str,
    files: list[tuple[str, str]],
    repo: Path,
    out_dir: Path,
) -> str:
    replacements = {
        "TARGET": shard["target"],
        "AUDIT_REPO": str(repo),
        "SHARD_FOCUS": shard["focus"],
        "TARGET_VALID_FINDINGS": "1",
        "AGENT_TEMPLATE": "tests/c4/src/lib.rs",
        "AGENT_UTILS": (
            "the K2 tests/c4 Setup::new scaffold, existing Rust/Soroban unit tests, "
            "integration tests, WASM-backed contract imports, and project Cargo workspace"
        ),
        "INPUT_NOTES": str(out_dir / f"{shard_name}_notes.md"),
        "INPUT_POC": "tests/c4/src/lib.rs",
        "AGENT_DIR": str(out_dir / shard_name),
        "AGENT_ID": shard_name,
    }
    rendered = render_prompt(base_prompt, replacements)
    file_sections = []
    for rel, text in files:
        language = code_fence_language(rel)
        file_sections.append(f"### {rel}\n```{language}\n{text}\n```")

    return "\n\n".join(
        [
            "# Code4rena K2 Formal Shard",
            rendered,
            "## K2 Contest Rules And Scope",
            contest_text,
            "## V12 And Public Exclusion Manifest",
            (
                "All V12 findings are out of scope. Public known issues in the contest README are also "
                "out of scope. Use this title manifest for duplicate avoidance; if a hypothesis matches "
                "one of these root-cause/impact families, reject it and continue."
            ),
            v12_manifest or "[No V12 manifest extracted.]",
            "## Shard Assignment",
            f"Shard name: {shard_name}",
            f"Target: {shard['target']}",
            f"Focus: {shard['focus']}",
            "## K2 Output Contract",
            (
                "Return a concise audit memo with these sections: "
                "1) confirmed findings, 2) strongest unconfirmed hypotheses, "
                "3) exact Rust PoC plan for tests/c4/src/lib.rs, "
                "4) commands to run, 5) files/functions needing manual inspection next. "
                "For High/Medium candidates, require a coded runnable PoC using tests/c4/src/lib.rs "
                "and the native command `bash build.sh && cargo test --package k2-c4 -- --nocapture`. "
                "Do not mark an issue confirmed unless the supplied source context is enough to build "
                "that PoC without changing production contracts. Explicitly reject V12 duplicates, "
                "public known issues, trusted-admin-only behavior, test-only behavior, and pure resource "
                "budget observations without direct security impact. Budget discipline: produce the final "
                "memo even if some reasoning is incomplete; do not spend the whole completion budget before "
                "writing the answer."
            ),
            "## Source Context",
            "\n\n".join(file_sections),
        ]
    )


def call_openrouter(
    *,
    api_key: str,
    model: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
    reasoning_effort: str | None,
    reasoning_max_tokens: int | None,
    include_reasoning: bool,
    timeout: int,
    retries: int,
) -> dict[str, Any]:
    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a senior Rust/Soroban smart-contract auditor working on a Code4rena contest. "
                    "Be skeptical, evidence-driven, and precise. Do not invent facts not present in the "
                    "supplied source context. Treat V12 and public known issues as out of scope."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if reasoning_max_tokens is not None:
        body["reasoning"] = {
            "max_tokens": reasoning_max_tokens,
            "exclude": not include_reasoning,
        }
    elif reasoning_effort:
        body["reasoning"] = {
            "effort": reasoning_effort,
            "exclude": not include_reasoning,
        }
    data = json.dumps(body).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/VPC-byte/agentflow",
        "X-Title": "agentflow-k2-formal-shard",
    }
    last_error: str | None = None
    for attempt in range(1, retries + 1):
        req = request.Request(OPENROUTER_URL, data=data, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            last_error = f"HTTP {exc.code}: {detail}"
        except Exception as exc:  # noqa: BLE001
            last_error = repr(exc)
        if attempt < retries:
            time.sleep(min(30, 2**attempt))
    raise RuntimeError(last_error or "OpenRouter request failed")


def extract_message(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return ""


def strip_reasoning(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: strip_reasoning(item)
            for key, item in value.items()
            if key not in {"reasoning", "reasoning_details"}
        }
    if isinstance(value, list):
        return [strip_reasoning(item) for item in value]
    return value


def write_outputs(
    *,
    out_dir: Path,
    shard_name: str,
    model: str,
    prompt_chars: int,
    files: list[tuple[str, str]],
    response: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    content = extract_message(response)
    usage = response.get("usage") or {}
    meta = {
        "shard": shard_name,
        "model": model,
        "response_model": response.get("model"),
        "id": response.get("id"),
        "created": response.get("created"),
        "usage": usage,
        "prompt_chars": prompt_chars,
        "context_files": [rel for rel, _ in files],
        "content_chars": len(content),
    }
    (out_dir / f"{shard_name}.meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    markdown = [
        f"# K2 Formal Shard: {shard_name}",
        "",
        f"Model: `{model}`",
        "",
        "## Context Files",
        "\n".join(f"- `{rel}`" for rel, _ in files),
        "",
        "## Model Output",
        content or "[No assistant content returned. Check meta/raw response.]",
    ]
    (out_dir / f"{shard_name}.md").write_text("\n".join(markdown), encoding="utf-8")
    sanitized = strip_reasoning(response)
    (out_dir / f"{shard_name}.raw.json").write_text(
        json.dumps(sanitized, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list-shards", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--shard", choices=sorted(SHARDS))
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--agentflow-repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--out-dir", type=Path, default=Path("k2-formal"))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-tokens", type=int, default=24_000)
    parser.add_argument("--temperature", type=float, default=0.12)
    parser.add_argument(
        "--reasoning-effort",
        choices=["none", "minimal", "low", "medium", "high", "xhigh"],
        default="none",
    )
    parser.add_argument("--reasoning-max-tokens", type=int)
    parser.add_argument("--include-reasoning", action="store_true")
    parser.add_argument("--timeout", type=int, default=1200)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--per-file-limit", type=int, default=120_000)
    parser.add_argument("--v12-manifest-limit", type=int, default=24_000)
    parser.add_argument("--prompt-file", default="prompts/code4rena-agentflow-triage-ensemble.md")
    parser.add_argument("--contest-file", default="code4rena/code4rena-k2.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.list_shards:
        for name, shard in SHARDS.items():
            print(f"{name}: {shard['target']}")
        return 0
    if not args.shard:
        print("--shard is required unless --list-shards is used", file=sys.stderr)
        return 2

    shard = SHARDS[args.shard]
    agentflow_repo = args.agentflow_repo.resolve()
    repo = args.repo.resolve()
    prompt_file = agentflow_repo / args.prompt_file
    contest_file = agentflow_repo / args.contest_file

    base_prompt = read_text(prompt_file)
    contest_text = read_text(contest_file)
    v12_manifest_limit = min(args.v12_manifest_limit, 8_000) if args.compact else args.v12_manifest_limit
    v12_manifest = extract_v12_manifest(repo, v12_manifest_limit)
    global_patterns = COMPACT_GLOBAL_PATTERNS if args.compact else GLOBAL_PATTERNS
    files = collect_context_files(
        repo,
        global_patterns + shard["patterns"],
        args.per_file_limit,
        skip_aux_tests=args.compact,
    )
    if not files:
        print(f"No context files matched for shard {args.shard} in {repo}", file=sys.stderr)
        return 1

    prompt = build_user_prompt(
        shard_name=args.shard,
        shard=shard,
        contest_text=contest_text,
        base_prompt=base_prompt,
        v12_manifest=v12_manifest,
        files=files,
        repo=repo,
        out_dir=args.out_dir.resolve(),
    )

    if args.dry_run:
        summary = {
            "shard": args.shard,
            "prompt_chars": len(prompt),
            "context_files": [rel for rel, _ in files],
            "v12_manifest_chars": len(v12_manifest),
            "compact": args.compact,
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("OPENROUTER_API_KEY is not set", file=sys.stderr)
        return 2

    response = call_openrouter(
        api_key=api_key,
        model=args.model,
        prompt=prompt,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        reasoning_effort=args.reasoning_effort,
        reasoning_max_tokens=args.reasoning_max_tokens,
        include_reasoning=args.include_reasoning,
        timeout=args.timeout,
        retries=args.retries,
    )
    write_outputs(
        out_dir=args.out_dir,
        shard_name=args.shard,
        model=args.model,
        prompt_chars=len(prompt),
        files=files,
        response=response,
    )
    print(args.out_dir / f"{args.shard}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
