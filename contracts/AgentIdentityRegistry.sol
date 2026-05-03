// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title AgentIdentityRegistry
/// @notice Minimal ERC-8004-style identity registry for hackathon demos.
contract AgentIdentityRegistry {
    uint256 public nextAgentId = 1;

    mapping(uint256 => address) public ownerOf;
    mapping(address => uint256) public agentIdOf;
    mapping(uint256 => string) public tokenURI;

    event AgentRegistered(uint256 indexed agentId, address indexed owner, string agentURI);
    event Transfer(address indexed from, address indexed to, uint256 indexed tokenId);

    error AlreadyRegistered();
    error NotRegistered();

    function registerAgent(string calldata agentURI) external returns (uint256 agentId) {
        if (agentIdOf[msg.sender] != 0) revert AlreadyRegistered();

        agentId = nextAgentId++;
        ownerOf[agentId] = msg.sender;
        agentIdOf[msg.sender] = agentId;
        tokenURI[agentId] = agentURI;

        emit Transfer(address(0), msg.sender, agentId);
        emit AgentRegistered(agentId, msg.sender, agentURI);
    }

    function setTokenURI(uint256 agentId, string calldata agentURI) external {
        if (ownerOf[agentId] != msg.sender) revert NotRegistered();
        tokenURI[agentId] = agentURI;
    }
}
