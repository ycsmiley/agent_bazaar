// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../AgentBazaarEscrow.sol";

/// @notice Minimal mintable ERC-20 used only for escrow tests.
contract MockUSDC {
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    function mint(address to, uint256 amount) external {
        balanceOf[to] += amount;
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        return true;
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        allowance[from][msg.sender] -= amount;
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        return true;
    }
}

contract AgentBazaarEscrowTest is Test {
    AgentBazaarEscrow escrow;
    MockUSDC usdc;

    address buyer = address(0xB0B);
    address seller = address(0x5E1);
    bytes32 rfq = keccak256("rfq-1");

    uint256 constant AMOUNT = 500_000; // 0.5 USDC
    uint64 constant DELIVERY = 600;    // 10 min
    uint64 constant DISPUTE = 300;     // 5 min

    function setUp() public {
        escrow = new AgentBazaarEscrow();
        usdc = new MockUSDC();
        usdc.mint(buyer, 10_000_000);
        vm.prank(buyer);
        usdc.approve(address(escrow), type(uint256).max);
    }

    function test_happyPath_buyerReleases() public {
        _lock();

        vm.prank(seller);
        escrow.confirmDelivery(rfq, keccak256("payload"));

        uint256 sellerBefore = usdc.balanceOf(seller);
        vm.prank(buyer);
        escrow.releaseFunds(rfq);
        assertEq(usdc.balanceOf(seller), sellerBefore + AMOUNT);
    }

    function test_optimisticRelease_afterDisputeWindow() public {
        _lock();
        vm.prank(seller);
        escrow.confirmDelivery(rfq, keccak256("payload"));

        vm.warp(block.timestamp + DISPUTE + 1);
        escrow.optimisticRelease(rfq);
        assertEq(usdc.balanceOf(seller), AMOUNT);
    }

    function test_optimisticRelease_revertsBeforeDeadline() public {
        _lock();
        vm.prank(seller);
        escrow.confirmDelivery(rfq, keccak256("payload"));

        vm.expectRevert(AgentBazaarEscrow.DeadlineNotPassed.selector);
        escrow.optimisticRelease(rfq);
    }

    function test_refund_afterDeliveryTimeout() public {
        _lock();
        vm.warp(block.timestamp + DELIVERY + 1);

        uint256 buyerBefore = usdc.balanceOf(buyer);
        escrow.claimRefund(rfq);
        assertEq(usdc.balanceOf(buyer), buyerBefore + AMOUNT);
    }

    function test_refund_revertsWithinDeliveryWindow() public {
        _lock();
        vm.expectRevert(AgentBazaarEscrow.DeadlineNotPassed.selector);
        escrow.claimRefund(rfq);
    }

    function test_dispute_freezesRelease() public {
        _lock();
        vm.prank(seller);
        escrow.confirmDelivery(rfq, keccak256("payload"));

        vm.prank(buyer);
        escrow.raiseDispute(rfq, "bad_payload");

        // After dispute, optimistic release must refuse (state != DELIVERED).
        vm.warp(block.timestamp + DISPUTE + 1);
        vm.expectRevert(
            abi.encodeWithSelector(
                AgentBazaarEscrow.InvalidState.selector,
                AgentBazaarEscrow.State.DISPUTED,
                AgentBazaarEscrow.State.DELIVERED
            )
        );
        escrow.optimisticRelease(rfq);
    }

    function test_rfqCannotBeReused() public {
        _lock();
        vm.prank(buyer);
        vm.expectRevert(AgentBazaarEscrow.RfqAlreadyUsed.selector);
        escrow.lockFunds(rfq, seller, AMOUNT, address(usdc), DELIVERY, DISPUTE);
    }

    function _lock() internal {
        vm.prank(buyer);
        escrow.lockFunds(rfq, seller, AMOUNT, address(usdc), DELIVERY, DISPUTE);
    }
}
