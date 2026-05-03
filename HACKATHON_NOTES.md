# Hackathon Notes

## New Work

Agent Bazaar's application code, contracts, demo service, tests, and submission
materials in this repository are the project work being submitted for Open
Agents.

Key new components include:

- RFQ, quote, delivery, and matching schemas.
- Buyer and seller agent flows.
- KeeperHub settlement client and workflow documentation.
- Escrow, MockUSDC, and ERC-8004-style identity/reputation contracts.
- Uniswap quote/check client and live quote proof script.
- Agent Bazaar live market screen and local demo service.
- Sponsor feedback artifacts and submission notes.

See [`DEVELOPMENT_PROCESS.md`](DEVELOPMENT_PROCESS.md) for the team-directed
planning and AI-assistance disclosure.

## Reused Open-Source Libraries

The project uses public libraries and standard tooling rather than custom forks:

- Python: `pydantic`, `httpx`, `web3`, `eth-account`, `python-dotenv`,
  `pynacl`, `rich`, `click`, `pytest`, `ruff`.
- Solidity/Foundry: `forge-std`.
- Browser demo: plain HTML/CSS/JavaScript with no external frontend framework.

## Not Included

- 0G and ENS integrations are intentionally not part of the final submission.
- The Uniswap integration is quote/check proof only for this hackathon path; the
  escrow settlement demo does not claim a Uniswap swap transaction.
