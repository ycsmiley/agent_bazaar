// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IAgentIdentityRegistry {
    function ownerOf(uint256 agentId) external view returns (address);
}

/// @title AgentReputationRegistry
/// @notice Minimal feedback registry compatible with Agent Bazaar's ERC-8004 client.
contract AgentReputationRegistry {
    struct Reputation {
        uint64 totalTasks;
        uint64 successCount;
        uint16 avgRatingBps;
    }

    address public immutable identityRegistry;

    mapping(uint256 => Reputation) private _reputation;

    event FeedbackSubmitted(
        uint256 indexed agentId,
        address indexed client,
        uint8 rating,
        string[] tags,
        string proofURI
    );

    error AgentNotRegistered();
    error SelfFeedback();
    error InvalidRating();

    constructor(address identityRegistry_) {
        identityRegistry = identityRegistry_;
    }

    function submitFeedback(
        uint256 agentId,
        uint8 rating,
        string[] calldata tags,
        string calldata proofURI
    ) external {
        if (rating > 5) revert InvalidRating();
        address owner = IAgentIdentityRegistry(identityRegistry).ownerOf(agentId);
        if (owner == address(0)) revert AgentNotRegistered();
        if (owner == msg.sender) revert SelfFeedback();

        Reputation storage rep = _reputation[agentId];
        uint256 totalRatingBps = uint256(rep.avgRatingBps) * rep.totalTasks;
        rep.totalTasks += 1;
        if (rating >= 4) rep.successCount += 1;
        rep.avgRatingBps = uint16((totalRatingBps + uint256(rating) * 2_000) / rep.totalTasks);

        emit FeedbackSubmitted(agentId, msg.sender, rating, tags, proofURI);
    }

    function getReputation(uint256 agentId)
        external
        view
        returns (uint64 totalTasks, uint64 successCount, uint16 avgRatingBps)
    {
        Reputation memory rep = _reputation[agentId];
        return (rep.totalTasks, rep.successCount, rep.avgRatingBps);
    }
}
