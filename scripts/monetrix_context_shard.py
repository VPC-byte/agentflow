#!/usr/bin/env python3
"""Run a focused Monetrix Code4rena context-pack shard through OpenRouter."""

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


SHARDS: dict[str, dict[str, Any]] = {
    "accountant_perp_cache": {
        "target": "MonetrixAccountant 4-gate settle pipeline and cached HyperCore asset registry state",
        "focus": (
            "Validate or disprove stale perpIndex / stale supplied-asset accounting paths. "
            "Trace notifyVaultSupply, addMultisigSupplyToken, config add/remove asset flows, "
            "PrecompileReader supplied-notional semantics, totalBackingSigned, surplus, "
            "distributableSurplus, and settleDailyPnL gates. Treat Governor/Operator-only "
            "misbehavior as out of scope unless a non-admin user path can trigger the unsafe state."
        ),
        "patterns": [
            "src/core/MonetrixAccountant.sol",
            "src/core/MonetrixConfig.sol",
            "src/core/MonetrixVault.sol",
            "src/core/PrecompileReader.sol",
            "src/core/TokenMath.sol",
            "src/interfaces/HyperCoreConstants.sol",
            "src/interfaces/IHyperCore.sol",
            "src/interfaces/IMonetrixAccountant.sol",
            "test/c4/C4Submission.t.sol",
            "test/MonetrixAccountant.t.sol",
            "test/Monetrix.t.sol",
            "test/**/MonetrixAccountant*.sol",
            "test/**/Mock*.sol",
        ],
    },
    "susdm_cooldown_escrow": {
        "target": "sUSDM cooldown, ERC-4626 accounting, and sUSDMEscrow isolation",
        "focus": (
            "Look for monotonic-rate violations, cooldownShares/cooldownAssets rounding, "
            "claimUnstake edge cases, totalPendingClaims desynchronization, escrow underfunding, "
            "yield injection interactions, and any in-scope user sequence that breaks INV-2 or INV-4."
        ),
        "patterns": [
            "src/tokens/sUSDM.sol",
            "src/tokens/sUSDMEscrow.sol",
            "src/tokens/USDM.sol",
            "src/core/MonetrixVault.sol",
            "src/core/YieldEscrow.sol",
            "src/core/TokenMath.sol",
            "test/c4/C4Submission.t.sol",
            "test/*sUSDM*.t.sol",
            "test/*SUSDM*.t.sol",
            "test/*USDM*.t.sol",
            "test/Monetrix.t.sol",
            "test/**/Mock*.sol",
        ],
    },
    "vault_redemption_bridge": {
        "target": "MonetrixVault redemption, bridge, escrow coverage, and bank-run flows",
        "focus": (
            "Audit requestRedeem, fundRedemptions, claimRedeem, keeperBridge, reclaim paths, "
            "bridge-principal accounting, RedeemEscrow totalOwed, pause/operator controls, "
            "and sustained-outflow scenarios. Prioritize loss, stuck funds, silent haircut, "
            "or coverage invariant breaks that do not depend purely on trusted operator abuse."
        ),
        "patterns": [
            "src/core/MonetrixVault.sol",
            "src/core/RedeemEscrow.sol",
            "src/core/ActionEncoder.sol",
            "src/core/MonetrixAccountant.sol",
            "src/core/MonetrixConfig.sol",
            "src/core/TokenMath.sol",
            "src/tokens/USDM.sol",
            "test/c4/C4Submission.t.sol",
            "test/*Vault*.t.sol",
            "test/*Redeem*.t.sol",
            "test/Monetrix.t.sol",
            "test/**/Mock*.sol",
        ],
    },
    "actionencoder_tokenmath_boundaries": {
        "target": "ActionEncoder, PrecompileReader, TokenMath, and HyperCore unit boundaries",
        "focus": (
            "Search for wire-format errors, uint64 truncation, signed/unsigned mistakes, "
            "decimal exponent overflow/underflow, fail-open decoding, malformed short-return "
            "precompile handling, and conversion bugs that can inflate backing, lose value, "
            "or break a Code4rena in-scope invariant."
        ),
        "patterns": [
            "src/core/ActionEncoder.sol",
            "src/core/PrecompileReader.sol",
            "src/core/TokenMath.sol",
            "src/core/MonetrixAccountant.sol",
            "src/core/MonetrixConfig.sol",
            "src/interfaces/HyperCoreConstants.sol",
            "src/interfaces/IHyperCore.sol",
            "test/c4/C4Submission.t.sol",
            "test/*Action*.t.sol",
            "test/*Precompile*.t.sol",
            "test/*TokenMath*.t.sol",
            "test/MonetrixAccountant.t.sol",
            "test/**/Mock*.sol",
        ],
    },
    "yield_distribution_cross_contract": {
        "target": "Yield distribution across MonetrixVault, MonetrixAccountant, YieldEscrow, sUSDM, InsuranceFund, and Foundation",
        "focus": (
            "Audit the full path settleDailyPnL -> YieldEscrow -> distributeYield -> "
            "sUSDM.injectYield / InsuranceFund / Foundation. Search for double counting, "
            "incorrect reserve checks, distribution before real EVM USDC arrives, "
            "APR/distributable cap bypasses, totalSettledYield desync, and bank-run interactions. "
            "A valid issue must show unbacked yield, stuck yield, insolvency, or broken accounting "
            "without relying only on trusted Operator/Governor misbehavior."
        ),
        "patterns": [
            "src/core/MonetrixVault.sol",
            "src/core/MonetrixAccountant.sol",
            "src/core/YieldEscrow.sol",
            "src/core/InsuranceFund.sol",
            "src/core/MonetrixConfig.sol",
            "src/tokens/sUSDM.sol",
            "src/tokens/USDM.sol",
            "test/c4/C4Submission.t.sol",
            "test/Monetrix.t.sol",
            "test/MonetrixAccountant.t.sol",
            "test/invariants/SolvencyInvariant.t.sol",
            "test/*Yield*.t.sol",
            "test/**/Mock*.sol",
        ],
    },
    "hedge_blp_action_paths": {
        "target": "Hedge, BLP, and CoreWriter action paths",
        "focus": (
            "Audit executeHedge, closeHedge, repairHedge, supplyToBlp, withdrawFromBlp, "
            "ActionEncoder payloads, pair-index validation, reduceOnly/tif semantics, "
            "spot/perp mismatches, residualBps handling, BLP supplied registry updates, "
            "and L1/EVM unit conversions. Prioritize wire-format or state desync bugs "
            "that can lose funds, mis-hedge assets, overstate backing, or permanently block operations."
        ),
        "patterns": [
            "src/core/MonetrixVault.sol",
            "src/core/ActionEncoder.sol",
            "src/core/MonetrixAccountant.sol",
            "src/core/MonetrixConfig.sol",
            "src/core/PrecompileReader.sol",
            "src/core/TokenMath.sol",
            "src/interfaces/HyperCoreConstants.sol",
            "src/interfaces/IHyperCore.sol",
            "test/c4/C4Submission.t.sol",
            "test/Monetrix.t.sol",
            "test/ActionEncoderBoundCheck.t.sol",
            "test/simulator/*.t.sol",
            "test/**/Mock*.sol",
        ],
    },
    "precompile_oracle_real_semantics": {
        "target": "HyperCore precompile read semantics, oracle formats, and simulator-vs-real assumptions",
        "focus": (
            "Cross-check PrecompileReader and TokenMath against existing simulator tests and real-semantics probes. "
            "Look for failures in tokenInfo/perpAssetInfo dynamic ABI decoding, oracle price scale assumptions, "
            "spotPx vs oraclePx confusion, suppliedBalance behavior, HLP equity units, and fail-closed handling. "
            "Explicitly separate already-fixed/test-documented issues from new in-scope findings."
        ),
        "patterns": [
            "src/core/PrecompileReader.sol",
            "src/core/TokenMath.sol",
            "src/core/MonetrixAccountant.sol",
            "src/core/MonetrixConfig.sol",
            "src/interfaces/HyperCoreConstants.sol",
            "src/interfaces/IHyperCore.sol",
            "test/c4/C4Submission.t.sol",
            "test/PrecisionBugPoC.t.sol",
            "test/TokenMathFuzz.t.sol",
            "test/simulator/*.t.sol",
            "test/MonetrixAccountant.t.sol",
            "lib/hyper-evm-lib/src/PrecompileLib.sol",
            "lib/hyper-evm-lib/src/CoreWriterLib.sol",
            "lib/hyper-evm-lib/test/unit-tests/vaults/VaultTest.t.sol",
        ],
    },
    "governance_pause_init_surface": {
        "target": "Access control, pause controls, UUPS initialization, and role-gated operational surface",
        "focus": (
            "Audit MonetrixAccessController, GovernedUpgradeable, UUPS initializers, role checks, pause/operatorPause "
            "coverage, emergency functions, and setters. Ignore pure trusted-admin power that contest rules exclude, "
            "but look for missing onlyRole, initializer takeover, pause bypass by user-facing flows, or role confusion "
            "that lets an untrusted user move funds or break accounting."
        ),
        "patterns": [
            "src/governance/*.sol",
            "src/core/MonetrixVault.sol",
            "src/core/MonetrixAccountant.sol",
            "src/core/MonetrixConfig.sol",
            "src/core/RedeemEscrow.sol",
            "src/core/YieldEscrow.sol",
            "src/core/InsuranceFund.sol",
            "src/tokens/*.sol",
            "test/c4/C4Submission.t.sol",
            "test/Governance.t.sol",
            "test/Monetrix.t.sol",
            "test/**/Mock*.sol",
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


def collect_context_files(repo: Path, patterns: list[str], per_file_limit: int) -> list[tuple[str, str]]:
    seen: set[Path] = set()
    files: list[tuple[str, str]] = []
    for pattern in patterns:
        matches = sorted(Path(p) for p in glob.glob(str(repo / pattern), recursive=True))
        for path in matches:
            if not path.is_file() or path in seen:
                continue
            seen.add(path)
            rel = path.relative_to(repo).as_posix()
            files.append((rel, read_text(path, per_file_limit)))
    return files


def build_user_prompt(
    *,
    shard_name: str,
    shard: dict[str, Any],
    contest_text: str,
    base_prompt: str,
    files: list[tuple[str, str]],
    repo: Path,
    out_dir: Path,
) -> str:
    replacements = {
        "TARGET": shard["target"],
        "AUDIT_REPO": str(repo),
        "SHARD_FOCUS": shard["focus"],
        "TARGET_VALID_FINDINGS": "1",
        "AGENT_TEMPLATE": "test/c4/C4Submission.t.sol",
        "AGENT_UTILS": "the repository's existing Foundry tests, mocks, deployment helpers, and test/c4 template",
        "INPUT_NOTES": str(out_dir / f"{shard_name}_notes.md"),
        "INPUT_POC": "test/c4/C4Submission.t.sol",
        "AGENT_DIR": str(out_dir / shard_name),
        "AGENT_ID": shard_name,
    }
    rendered = render_prompt(base_prompt, replacements)
    file_sections = []
    for rel, text in files:
        file_sections.append(f"### {rel}\n```solidity\n{text}\n```")

    return "\n\n".join(
        [
            "# Code4rena Monetrix Formal Shard",
            rendered,
            "## Contest Rules And Scope",
            contest_text,
            "## Shard Assignment",
            f"Shard name: {shard_name}",
            f"Target: {shard['target']}",
            f"Focus: {shard['focus']}",
            "## Output Contract",
            (
                "Return a concise audit memo with these sections: "
                "1) confirmed findings, 2) strongest unconfirmed hypotheses, "
                "3) exact PoC plan for test/c4/C4Submission.t.sol, "
                "4) commands to run, 5) files/functions needing manual inspection next. "
                "Do not mark an issue confirmed unless the provided code path is enough to make "
                "a runnable Foundry PoC. Explicitly reject paths that are only trusted Governor, "
                "UPGRADER, DEFAULT_ADMIN, or pure Operator compromise. "
                "Budget discipline: produce the final memo even if some reasoning is incomplete; "
                "do not spend the whole completion budget before writing the answer."
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
    timeout: int,
    retries: int,
) -> dict[str, Any]:
    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a senior smart-contract auditor working on a Code4rena contest. "
                    "Be skeptical, evidence-driven, and precise. Do not invent facts not present "
                    "in the supplied source context."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    data = json.dumps(body).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/VPC-byte/agentflow",
        "X-Title": "agentflow-monetrix-formal-shard",
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
        f"# Monetrix Formal Shard: {shard_name}",
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
    parser.add_argument("--shard", choices=sorted(SHARDS))
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--agentflow-repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--out-dir", type=Path, default=Path("monetrix-formal"))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-tokens", type=int, default=10000)
    parser.add_argument("--temperature", type=float, default=0.15)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--per-file-limit", type=int, default=140_000)
    parser.add_argument("--prompt-file", default="prompts/code4rena-agentflow-triage-ensemble.md")
    parser.add_argument("--contest-file", default="code4rena/code4rena-monetrix.md")
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

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("OPENROUTER_API_KEY is not set", file=sys.stderr)
        return 2

    shard = SHARDS[args.shard]
    agentflow_repo = args.agentflow_repo.resolve()
    repo = args.repo.resolve()
    prompt_file = agentflow_repo / args.prompt_file
    contest_file = agentflow_repo / args.contest_file

    base_prompt = read_text(prompt_file)
    contest_text = read_text(contest_file)
    files = collect_context_files(repo, shard["patterns"], args.per_file_limit)
    if not files:
        print(f"No context files matched for shard {args.shard} in {repo}", file=sys.stderr)
        return 1

    prompt = build_user_prompt(
        shard_name=args.shard,
        shard=shard,
        contest_text=contest_text,
        base_prompt=base_prompt,
        files=files,
        repo=repo,
        out_dir=args.out_dir.resolve(),
    )
    response = call_openrouter(
        api_key=api_key,
        model=args.model,
        prompt=prompt,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
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
