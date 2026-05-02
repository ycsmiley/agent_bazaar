// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice Minimal ERC-20 surface used by the escrow.
interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
}

/// @title AgentBazaarEscrow
/// @notice Conditional escrow closing x402's pay-then-deliver trust gap.
/// @dev State machine: OPEN → LOCKED → DELIVERED → RELEASED
///      Alt paths: LOCKED → REFUNDED (delivery timeout)
///                 DELIVERED → DISPUTED (buyer rejects) or RELEASED via optimistic release.
contract AgentBazaarEscrow {
    enum State {
        OPEN,
        LOCKED,
        DELIVERED,
        RELEASED,
        DISPUTED,
        REFUNDED
    }

    struct Deal {
        bytes32 rfqId;
        address buyer;
        address seller;
        uint256 amount;
        address token;
        uint64 deliveryDeadline;
        uint64 disputeDeadline;
        bytes32 resultHash;
        State state;
    }

    mapping(bytes32 => Deal) private _deals;

    event FundsLocked(
        bytes32 indexed rfqId,
        address indexed buyer,
        address indexed seller,
        uint256 amount,
        address token,
        uint64 deliveryDeadline
    );
    event DeliveryConfirmed(bytes32 indexed rfqId, bytes32 resultHash, uint64 disputeDeadline);
    event FundsReleased(bytes32 indexed rfqId, address indexed seller, uint256 amount);
    event OptimisticRelease(bytes32 indexed rfqId);
    event DisputeRaised(bytes32 indexed rfqId, address indexed buyer, string reason);
    event Refunded(bytes32 indexed rfqId, address indexed buyer, uint256 amount);

    error InvalidState(State actual, State expected);
    error NotAuthorized();
    error DeadlinePassed();
    error DeadlineNotPassed();
    error InvalidAmount();
    error RfqAlreadyUsed();

    /// @notice Buyer locks funds for a specific RFQ / seller.
    function lockFunds(
        bytes32 rfqId,
        address seller,
        uint256 amount,
        address token,
        uint64 deliveryWindowSecs,
        uint64 disputeWindowSecs
    ) external {
        if (_deals[rfqId].buyer != address(0)) revert RfqAlreadyUsed();
        if (amount == 0) revert InvalidAmount();
        if (seller == address(0)) revert NotAuthorized();

        uint64 deliveryDeadline = uint64(block.timestamp) + deliveryWindowSecs;

        _deals[rfqId] = Deal({
            rfqId: rfqId,
            buyer: msg.sender,
            seller: seller,
            amount: amount,
            token: token,
            deliveryDeadline: deliveryDeadline,
            disputeDeadline: disputeWindowSecs,
            resultHash: bytes32(0),
            state: State.LOCKED
        });

        bool ok = IERC20(token).transferFrom(msg.sender, address(this), amount);
        require(ok, "transferFrom failed");

        emit FundsLocked(rfqId, msg.sender, seller, amount, token, deliveryDeadline);
    }

    /// @notice Seller posts the delivery hash for the canonical result payload.
    function confirmDelivery(bytes32 rfqId, bytes32 resultHash) external {
        Deal storage deal = _deals[rfqId];
        if (msg.sender != deal.seller) revert NotAuthorized();
        if (deal.state != State.LOCKED) revert InvalidState(deal.state, State.LOCKED);
        if (block.timestamp > deal.deliveryDeadline) revert DeadlinePassed();

        deal.resultHash = resultHash;
        // `disputeDeadline` was storing the window at lock-time; convert it to an absolute deadline now.
        deal.disputeDeadline = uint64(block.timestamp) + deal.disputeDeadline;
        deal.state = State.DELIVERED;

        emit DeliveryConfirmed(rfqId, resultHash, deal.disputeDeadline);
    }

    /// @notice Buyer signs off → seller gets paid.
    function releaseFunds(bytes32 rfqId) external {
        Deal storage deal = _deals[rfqId];
        if (msg.sender != deal.buyer) revert NotAuthorized();
        if (deal.state != State.DELIVERED) revert InvalidState(deal.state, State.DELIVERED);
        _release(rfqId);
    }

    /// @notice KeeperHub-driven release after the buyer's dispute window expires.
    function optimisticRelease(bytes32 rfqId) external {
        Deal storage deal = _deals[rfqId];
        if (deal.state != State.DELIVERED) revert InvalidState(deal.state, State.DELIVERED);
        if (block.timestamp <= deal.disputeDeadline) revert DeadlineNotPassed();
        _release(rfqId);
        emit OptimisticRelease(rfqId);
    }

    /// @notice Buyer flags a bad delivery within the dispute window. Resolution is off-chain for MVP.
    function raiseDispute(bytes32 rfqId, string calldata reason) external {
        Deal storage deal = _deals[rfqId];
        if (msg.sender != deal.buyer) revert NotAuthorized();
        if (deal.state != State.DELIVERED) revert InvalidState(deal.state, State.DELIVERED);
        if (block.timestamp > deal.disputeDeadline) revert DeadlinePassed();
        deal.state = State.DISPUTED;
        emit DisputeRaised(rfqId, msg.sender, reason);
    }

    /// @notice Seller missed the delivery window → buyer (or a keeper) can claim a refund.
    function claimRefund(bytes32 rfqId) external {
        Deal storage deal = _deals[rfqId];
        if (deal.state != State.LOCKED) revert InvalidState(deal.state, State.LOCKED);
        if (block.timestamp <= deal.deliveryDeadline) revert DeadlineNotPassed();

        deal.state = State.REFUNDED;
        bool ok = IERC20(deal.token).transfer(deal.buyer, deal.amount);
        require(ok, "refund transfer failed");

        emit Refunded(rfqId, deal.buyer, deal.amount);
    }

    /// @notice Deal getter — external reads return a struct-less tuple for ergonomic ABI usage.
    function getDeal(bytes32 rfqId)
        external
        view
        returns (
            address buyer,
            address seller,
            uint256 amount,
            address token,
            uint64 deliveryDeadline,
            uint64 disputeDeadline,
            bytes32 resultHash,
            State state
        )
    {
        Deal memory d = _deals[rfqId];
        return (
            d.buyer,
            d.seller,
            d.amount,
            d.token,
            d.deliveryDeadline,
            d.disputeDeadline,
            d.resultHash,
            d.state
        );
    }

    function _release(bytes32 rfqId) internal {
        Deal storage deal = _deals[rfqId];
        deal.state = State.RELEASED;
        bool ok = IERC20(deal.token).transfer(deal.seller, deal.amount);
        require(ok, "release transfer failed");
        emit FundsReleased(rfqId, deal.seller, deal.amount);
    }
}
