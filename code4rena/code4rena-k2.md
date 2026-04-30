https://github.com/code-423n4/2026-04-k2
K2
K2 brings sophisticated DeFi lending to Stellar through pooled, isolated, and gated markets. Built for RWAs, AI agents, and institutions, with an integrated UI and real-time risk dashboards.

about 1 month
$135,000 in USDC
Apr 18, 4:00 AM GMT+8
May 28, 4:00 AM GMT+8
Details
Your submissions
Q&A
K2 audit details
Total Prize Pool: $135,000 in USDC
HM awards: up to $120,000 in USDC
If no valid Highs or Mediums are found, the HM pool is $0
QA awards: $5,000 in USDC
Judge awards: $9,500 in USDC
Scout awards: $500 USDC
Read our guidelines for more details
Starts April 17, 2026 20:00 UTC
Ends May 27, 2026 20:00 UTC
❗ Important notes for wardens
Since this audit includes live/deployed code, all submissions will be treated as sensitive:
Wardens are encouraged to submit High-risk submissions affecting live code promptly, to ensure timely disclosure of such vulnerabilities to the sponsor and guarantee payout in the case where a sponsor patches a live critical during the audit.
Submissions will be hidden from all wardens (SR and non-SR alike) by default, to ensure that no sensitive issues are erroneously shared.
If the submissions include findings affecting live code, there will be no post-judging QA phase. This ensures that awards can be distributed in a timely fashion, without compromising the security of the project. (Senior members of C4 staff will review the judges’ decisions per usual.)
By default, submissions will not be made public until the report is published.
Exception: if the sponsor indicates that no submissions affect live code, then we’ll make submissions visible to all authenticated wardens, and open PJQA to SR wardens per the usual C4 process.
The "live criticals" exception therefore applies.
A coded, runnable PoC is required for all High/Medium submissions to this audit.
This repo includes a basic template to run the test suite, located at tests/c4/src/lib.rs.
PoCs must use the test_submission_validity test in tests/c4 as their starting point. Extend that function (or add sibling #[test]s in the same file) to demonstrate your finding.
Your submission will be marked as Insufficient if the PoC is not runnable and working with the provided test suite.
Exception: PoC is optional (though recommended) for wardens with signal ≥ 0.4.
Judging phase risk adjustments (upgrades/downgrades):
High- or Medium-risk submissions downgraded by the judge to Low-risk (QA) will be ineligible for awards.
Upgrading a Low-risk finding from a QA report to a Medium- or High-risk finding is not supported.
As such, wardens are encouraged to select the appropriate risk level carefully during the submission phase.
V12 findings
V12 is Zellic's in-house AI auditing tool. It is the only autonomous auditor that reliably finds Highs and Criticals. All issues found by V12 will be judged as out of scope and ineligible for awards.

V12 findings can be viewed in the files below, or here:

Critical severity output
High severity output
Medium and Low severity output
Publicly known issues
Anything included in this section is considered a publicly known issue and is therefore ineligible for awards.

Self-liquidation: Users can liquidate their own positions. This follows Aave V3 precedent and provides a mechanism for users to efficiently unwind positions.
Flash liquidation memory budget: The two-step flash liquidation (prepare_liquidation + execute_liquidation) with a swap handler exceeds Soroban's 42 MB memory limit at 2+ reserves. Regular liquidation_call works up to ~6-7 reserves per user bitmap. This is a known Soroban VM constraint, not a protocol bug.
DEX integration: Depth and liquidity of DEX pools that may impact liquidation is a known issue and is considered risk-parameter related and out of scope.
Overview
K2 is a decentralized borrowing and lending protocol built on Stellar's Soroban smart-contract platform. It adapts the proven design patterns of Aave V3 to Stellar's unique constraints, and lets users:

Supply assets to earn interest (receive interest-bearing aTokens)
Borrow assets against collateral at variable rates
Liquidate undercollateralized positions
Flash loan assets for atomic operations
The protocol is organized around a router contract (kinetic-router) that serves as the single entry point for all user operations. Interest accrues per-reserve via scaled balances divided by monotonically-increasing liquidity and borrow indices, matching the Aave V3 accounting model.

Stellar-Specific Design Considerations
The implementation addresses several Soroban-specific constraints and capabilities:

Two-step flash liquidation: Soroban's 100M CPU instruction limit per transaction necessitates splitting liquidation into separate prepare_liquidation and execute_liquidation calls when a swap handler is involved.
Bitmap user configuration: User reserve participation is tracked with a 128-bit bitmap (2 bits per reserve: collateral flag + borrowing flag), supporting up to 64 reserves per pool.
Oracle cascade: Prices are resolved in priority order (Manual Override → Custom Oracle → Reflector → Fallback Oracle) with a 20% circuit breaker that freezes the cache on anomalous price changes.
U256 intermediate math: Value calculations use U256 intermediates to prevent overflow in balance × price × oracle_to_wad / decimals expressions across mixed-decimal assets.
Separated admin roles: The emergency admin can pause but cannot unpause, ensuring that a compromised emergency key cannot unilaterally resume protocol operations.
Links
Previous audits:
Halborn Security - September 2025
WatchPug - 4 audit rounds, October 2025 – March 2026
Documentation: docs/
Website: https://www.k2lend.com
X/Twitter: https://x.com/K2_Lend
Scope
Files in scope
Note: The nSLoC counts in the following table have been automatically generated and may differ depending on the definition of what a "significant" line of code represents. As such, they should be considered indicative rather than absolute representations of the lines involved in each contract.

Contract	SLoC
contracts/shared/src/utils.rs	402
contracts/shared/src/dex.rs	362
contracts/shared/src/types.rs	199
contracts/shared/src/upgradeable.rs	162
contracts/shared/src/errors.rs	139
contracts/shared/src/events.rs	111
contracts/shared/src/constants.rs	66
contracts/shared/src/lib.rs	21
contracts/kinetic-router/src/router.rs	1,296
contracts/kinetic-router/src/calculation.rs	963
contracts/kinetic-router/src/storage.rs	851
contracts/kinetic-router/src/liquidation.rs	561
contracts/kinetic-router/src/flash_loan.rs	452
contracts/kinetic-router/src/operations.rs	432
contracts/kinetic-router/src/reserve.rs	395
contracts/kinetic-router/src/validation.rs	392
contracts/kinetic-router/src/swap.rs	269
contracts/kinetic-router/src/params.rs	231
contracts/kinetic-router/src/admin.rs	146
contracts/kinetic-router/src/price.rs	111
contracts/kinetic-router/src/treasury.rs	99
contracts/kinetic-router/src/access_control.rs	90
contracts/kinetic-router/src/events.rs	48
contracts/kinetic-router/src/views.rs	42
contracts/kinetic-router/src/upgrade.rs	23
contracts/kinetic-router/src/lib.rs	22
contracts/kinetic-router/src/emergency.rs	15
contracts/pool-configurator/src/reserve.rs	747
contracts/pool-configurator/src/contract.rs	427
contracts/pool-configurator/src/storage.rs	133
contracts/pool-configurator/src/oracle.rs	72
contracts/pool-configurator/src/upgrade.rs	15
contracts/pool-configurator/src/lib.rs	11
contracts/a-token/src/contract.rs	592
contracts/a-token/src/storage.rs	92
contracts/a-token/src/balance.rs	80
contracts/a-token/src/upgrade.rs	18
contracts/a-token/src/lib.rs	9
contracts/debt-token/src/contract.rs	286
contracts/debt-token/src/storage.rs	69
contracts/debt-token/src/balance.rs	59
contracts/debt-token/src/upgrade.rs	18
contracts/debt-token/src/lib.rs	9
contracts/price-oracle/src/contract.rs	626
contracts/price-oracle/src/oracle.rs	371
contracts/price-oracle/src/storage.rs	283
contracts/price-oracle/src/upgrade.rs	18
contracts/price-oracle/src/lib.rs	10
contracts/interest-rate-strategy/src/contract.rs	250
contracts/interest-rate-strategy/src/storage.rs	107
contracts/interest-rate-strategy/src/validation.rs	32
contracts/interest-rate-strategy/src/upgrade.rs	15
contracts/interest-rate-strategy/src/lib.rs	10
contracts/liquidation-engine/src/storage.rs	233
contracts/liquidation-engine/src/contract.rs	200
contracts/liquidation-engine/src/calculation.rs	116
contracts/liquidation-engine/src/admin.rs	36
contracts/liquidation-engine/src/types.rs	21
contracts/liquidation-engine/src/upgrade.rs	18
contracts/liquidation-engine/src/validation.rs	16
contracts/liquidation-engine/src/lib.rs	14
contracts/incentives/src/contract.rs	606
contracts/incentives/src/storage.rs	345
contracts/incentives/src/calculation.rs	78
contracts/incentives/src/events.rs	69
contracts/incentives/src/error.rs	30
contracts/incentives/src/lib.rs	10
contracts/treasury/src/contract.rs	161
contracts/treasury/src/storage.rs	159
contracts/treasury/src/events.rs	35
contracts/treasury/src/error.rs	28
contracts/treasury/src/lib.rs	8
contracts/flash-liquidation-helper/src/validation.rs	92
contracts/flash-liquidation-helper/src/error.rs	29
contracts/flash-liquidation-helper/src/lib.rs	24
contracts/token/src/contract.rs	172
contracts/token/src/storage.rs	108
contracts/token/src/lib.rs	10
contracts/token/src/types.rs	7
contracts/aquarius-swap-adapter/src/lib.rs	260
contracts/soroswap-swap-adapter/src/lib.rs	343
Total	15,487
 
For a machine-readable version, see scope.txt.

Files out of scope
File/Directory	File Count
contracts/kinetic-router/fuzz/* (fuzz harnesses and corpora)	23
tests/* (unit tests, integration tests, and PoC submission template)	81
external/* (mock Reflector / Soroswap WASMs used in tests)	4
Total	108
 
For a machine-readable version, see out_of_scope.txt.

Additional context
Areas of concern (where to focus for bugs)
Solvency accounting & interest indices: Correctness of scaled-balance math, monotonicity of liquidity_index and variable_borrow_index, rounding direction, and the relationship between aToken_total_supply_scaled × liquidity_index and underlying_balance + total_debt_scaled × borrow_index.
Health factor & liquidation math: Post-liquidation health factor improvement enforcement, partial vs full liquidation, liquidation bonus calculation, and bad debt socialization via deficit tracking.
Oracle safety: Price cache TTL, staleness rejection, circuit breaker behaviour on large price moves, and the fallback cascade ordering (Manual Override → Custom Oracle → Reflector → Fallback).
Flash loan & flash liquidation atomicity: Premium collection (must always round up), repayment enforcement within the same transaction, and state consistency across the prepare_liquidation / execute_liquidation split.
Bitmap bounds & reserve indexing: 64-reserve limit enforcement, reserve index collision after reserve drop and re-registration, and UserConfig bitmap state transitions across supply / withdraw / borrow / repay.
DEX adapter integration: Slippage bounds (min_swap_output_bps), swap-handler whitelist enforcement, and minimum output calculation on both the Aquarius and Soroswap adapters.
Admin role separation & upgrades: Two-step admin transfer, the asymmetry where emergency admin can pause but cannot unpause, per-contract upgrade authority, and the WASM upgrade flow.
Reserve caps & debt ceilings: Supply cap, borrow cap, and minimum-remaining-debt enforcement under concurrent operations, including interactions with interest accrual rounding.
Authorization boundaries: require_auth() coverage at every state-changing entry point, repay-on-behalf authorization (repayer.require_auth() vs user.require_auth()), and emergency admin scope limits.
Multi-asset U256 math: Overflow and precision in balance × price × oracle_to_wad / decimals across mixed-decimal assets.
Main invariants
Solvency & Accounting

Conservation of value: For every reserve, aToken_total_supply_scaled * liquidity_index must not exceed underlying_token_balance + total_debt_scaled * borrow_index (modulo accrued protocol fees)
No phantom value creation: aToken minting/burning must exactly correspond to underlying token deposits/withdrawals. Debt token minting/burning must exactly correspond to borrows/repayments.
Supply-debt consistency: sum(user_scaled_balances) == total_supply_scaled for both aToken and debtToken contracts at all times
Health Factor & Collateralization

Borrowing collateralization: After any borrow or withdraw, the user's health factor must be ≥ 1.0 WAD (1e18), or the transaction reverts with HealthFactorTooLow (Error #8)
Liquidation improvement: After any liquidation, the borrower's health factor must improve (or remain within LIQUIDATION_HF_TOLERANCE_BPS = 1 bp tolerance for rounding noise)
Liquidation eligibility: Only positions with health factor < HEALTH_FACTOR_LIQUIDATION_THRESHOLD (1.0 WAD) can be liquidated
Index Monotonicity

Liquidity index is non-decreasing: liquidity_index(t+1) >= liquidity_index(t) - interest always accrues forward
Borrow index is non-decreasing: variable_borrow_index(t+1) >= variable_borrow_index(t) - no interest regression
Indices never drop below RAY: Both indices start at RAY (1e27) and can only increase
Authorization

Privileged operations require authorization: All admin, configuration, and treasury operations require require_auth() from the appropriate role
Emergency admin asymmetry: Emergency admin can pause but CANNOT unpause - only pool admin can unpause
User operations require user auth: Supply, borrow, repay, withdraw all require user.require_auth() (except repay-on-behalf, which requires repayer.require_auth())
Flash Loans

Atomicity: Flash loaned assets must be repaid with premium within the same transaction, or the transaction reverts with FlashLoanNotRepaid
Premium collection: Flash loan premium is always collected and rounds UP (percent_mul_up) - the protocol never receives less than the expected fee
Protocol Safety

Pause halts all state-changing operations: When paused, all user operations (supply, borrow, repay, withdraw, liquidation, flash loan, swap) revert with AssetPaused. Read-only queries remain functional.
Reserve capacity limits: Supply and borrow caps are enforced - no reserve can exceed its configured cap
Bitmap bounds: User configuration bitmap supports at most 64 reserves (2 bits per reserve). reserve_index >= 64 is rejected
All trusted roles in the protocol
Role	Description
Pool Admin	- Initializes and configures reserves (via pool-configurator)
- Updates risk parameters: LTV, liquidation threshold, liquidation bonus, reserve factor
- Sets supply/borrow caps, min remaining debt, debt ceiling
- Sets flash loan premium (max 100 bps)
- Sets/changes treasury, incentives, DEX router/factory addresses
- Sets swap handler whitelist, reserve whitelists/blacklists, liquidation whitelists/blacklists
- Unpauses the protocol (emergency admin cannot)
- Proposes new pool admin or emergency admin (two-step transfer)
- Upgrades contract WASM
- Flushes oracle config cache
Emergency Admin	- pause() - halts all user operations
- Cannot unpause, configure reserves, or perform any other admin action
- Rationale: separation ensures a compromised emergency key cannot unilaterally resume operations after an attack
Oracle Admin	- Adds/removes assets from oracle
- Sets manual price override (with expiry timestamp)
- Sets custom oracle, fallback oracle, batch oracle per asset
- Sets price cache TTL
- Configures/resets circuit breaker
- Pauses/unpauses the oracle
Pool Configurator Admin	- Deploys and initializes new reserves (deploys aToken + debtToken contracts)
- Configures collateral parameters
- Updates interest rate strategy per reserve
- Drops reserves
Emission Manager (Incentives)	- Configures per-asset reward emissions
- Sets emission rate (tokens/second)
- Sets distribution end timestamp
- Funds reward pool with tokens
- Pauses/unpauses incentives
Treasury Admin	- Withdraws accumulated protocol fees
- Syncs token balances
Interest Rate Strategy Admin	- Sets base variable borrow rate
- Sets variable rate slope 1 and slope 2
Upgrade Admin (per contract)	- upgrade(new_wasm_hash) - replaces contract bytecode
- Two-step transfer: propose_admin → accept_admin
 
Current holders (all roles): The deployer key initially holds every role above. The migration target is a Volta 2-of-5 multisig for the pool admin, with a separate key for the emergency admin.

Running tests
git clone https://github.com/code-423n4/2026-04-k2
cd 2026-04-k2
Prerequisites:

Rust (stable) with the wasm32v1-none target (automatically installed via rust-toolchain.toml when using rustup)
Stellar CLI for building WASM contracts
Build all contracts to WASM (compile + optimize):

./build.sh
Run the PoC test suite (the starting point for warden submissions):

cargo test --package k2-c4
Run the full unit test suite:

cargo test --package k2-unit-tests
Run the integration test suite:

cargo test --package k2-integration-tests
Miscellaneous
Employees of K2 and employees' family members are ineligible to participate in this audit.

Code4rena's rules cannot be overridden by the contents of this README. In case of doubt, please check with C4 staff.