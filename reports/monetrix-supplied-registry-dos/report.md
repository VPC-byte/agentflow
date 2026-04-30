# BLP supplied-registry entries can fail-closed and temporarily block settlement

Risk level: QA / Low candidate. Do not submit as High or Medium unless Code4rena staff or judging guidance treats trusted-Operator operational DoS as in scope.

## Summary

`MonetrixVault.supplyToBlp` immediately registers a supplied asset in `MonetrixAccountant` after emitting the HyperCore `BORROW_LEND` action. If the corresponding HyperCore 0x811 supplied-balance slot is not actually activated or later becomes unavailable, `MonetrixAccountant.totalBackingSigned()` reverts when it iterates the registered slot. Because `settleDailyPnL` calls `distributableSurplus()`, this also blocks `Vault.settle`.

The condition is recoverable: an Operator can remove the stale entry with `removeSuppliedEntry`. This is why this is best treated as a QA/Low operational robustness issue rather than an HM finding.

## Vulnerability Details

`supplyToBlp` sends the L1 supply action and then registers the supplied token without on-chain confirmation that the L1 0x811 slot is usable:

```solidity
function supplyToBlp(uint64 token, uint64 l1Amount) external onlyOperator whenOperatorNotPaused {
    require(l1Amount > 0, "zero amount");
    ActionEncoder.sendSupply(token, l1Amount);
    if (accountant != address(0)) {
        uint32 perpIndex = 0;
        if (token != uint64(HyperCoreConstants.USDC_TOKEN_INDEX)) {
            require(config.isSpotWhitelisted(uint32(token)), "spot not whitelisted");
            perpIndex = config.spotToPerp(uint32(token));
        }
        MonetrixAccountant(accountant).notifyVaultSupply(token, perpIndex);
    }
    emit BlpSupplied(token, l1Amount);
}
```

Once registered, `_readL1Backing` strictly reads every supplied registry entry:

```solidity
for (uint256 i = 0; i < slen; i++) {
    SuppliedAsset storage a = suppliedList[i];
    if (a.spotToken == uint64(HyperCoreConstants.USDC_TOKEN_INDEX)) {
        total += int256(PrecompileReader.suppliedUsdcEvm(account));
    } else {
        total += int256(
            PrecompileReader.suppliedNotionalUsdcFromPerp(uint32(a.spotToken), a.perpIndex, account)
        );
    }
}
```

`PrecompileReader.suppliedBalance` is intentionally fail-closed:

```solidity
require(ok && res.length >= 128, "PrecompileReader: supplied balance read failed");
```

That means a stale or prematurely registered supplied slot reverts the whole backing read, which blocks `surplus`, `distributableSurplus`, and `settleDailyPnL`.

## Impact

The immediate impact is temporary denial of service for yield settlement while the stale supplied-registry entry remains present. It does not directly steal funds or inflate backing. The issue is recoverable by an Operator calling:

```solidity
accountant.removeSuppliedEntry(false, index);
```

Scope caveat: the trigger is tied to the trusted `OPERATOR` BLP pipeline. The contest README explicitly says the Operator is trusted and has immediate authority over bridge, hedge, yield, BLP, and HLP pipelines. Risks arising purely from Operator invalid actions or inaction are likely out of scope for HM judging.

## Proof of Concept

Edit `test/c4/C4Submission.t.sol` in place and replace only `test_submissionValidity` with the body below.

```solidity
function test_submissionValidity() public {
    uint32 hypePerp = 4;
    uint32 hypeToken = 1105;
    uint32 hypePairAsset = 11105;

    _deposit(user1, 10_000e6);
    usdc.mint(address(vault), 100e6);

    vm.prank(admin);
    config.addTradeableAsset(
        MonetrixConfig.TradeableAsset({
            perpIndex: hypePerp,
            spotIndex: hypeToken,
            spotPairAssetId: hypePairAsset
        })
    );

    vm.mockCallRevert(
        HyperCoreConstants.PRECOMPILE_SUPPLIED_BALANCE,
        abi.encode(address(vault), uint64(hypeToken)),
        "supplied precompile unavailable"
    );

    // With no supplied registry entry, the accountant does not touch 0x811
    // for HYPE. The failing precompile is only reached after registration.
    accountant.totalBackingSigned();
    assertEq(accountant.vaultSuppliedLength(), 0);

    vm.prank(operator);
    vault.supplyToBlp(uint64(hypeToken), 5e8);

    (uint64 registeredToken, uint32 registeredPerp) = accountant.vaultSupplied(0);
    assertEq(registeredToken, uint64(hypeToken));
    assertEq(registeredPerp, hypePerp);

    vm.expectRevert(bytes("PrecompileReader: supplied balance read failed"));
    accountant.totalBackingSigned();

    vm.warp(block.timestamp + 21 hours);
    vm.prank(operator);
    vm.expectRevert(bytes("PrecompileReader: supplied balance read failed"));
    vault.settle(1e6);

    vm.prank(operator);
    accountant.removeSuppliedEntry(false, 0);

    assertEq(accountant.vaultSuppliedLength(), 0);
    accountant.totalBackingSigned();

    vm.prank(operator);
    vault.settle(1e6);
    assertEq(usdc.balanceOf(address(yieldEscrow)), 1e6);
}
```

Run:

```bash
env -u FOUNDRY_ETH_RPC_URL -u ETH_RPC_URL forge test --match-path test/c4/C4Submission.t.sol -vvvv
```

Observed result:

```text
Ran 1 test for test/c4/C4Submission.t.sol:C4Submission
[PASS] test_submissionValidity() (gas: 674818)
Suite result: ok. 1 passed; 0 failed; 0 skipped
```

Additional regression checks:

```bash
env -u FOUNDRY_ETH_RPC_URL -u ETH_RPC_URL forge test --match-path test/simulator/SuppliedRegistry.t.sol -vvv
# 9 passed

env -u FOUNDRY_ETH_RPC_URL -u ETH_RPC_URL forge test --match-test test_suppliedBalance_revertsWhenNeverSupplied -vvv
# 1 passed

env -u FOUNDRY_ETH_RPC_URL -u ETH_RPC_URL forge test --match-path test/simulator/BlpAction.t.sol -vvv
# 3 passed
```

## Recommended Mitigation

Consider one of:

- Register supplied slots only after an observed successful 0x811 activation.
- Add an Operator helper that verifies and prunes stale supplied entries in one transaction.
- Add explicit events and runbook text around stale 0x811 supplied-slot cleanup.
- If fail-closed settlement DoS is not desired, make supplied-slot reads tolerate a missing slot as zero, with an event. This trades operational liveness for the current fail-closed accounting posture.

## Tools Used

Manual review, Foundry, Kimi 2.5 shard analysis.
