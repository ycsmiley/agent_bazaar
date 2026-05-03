# AI Tool Usage Disclosure

ETHGlobal permits AI-assisted development, but asks teams to document how AI
tools were used. This project used AI assistance as an engineering copilot, not
as a replacement for team direction.

## Tools Used

- OpenAI ChatGPT / Codex for code review, implementation assistance, test
  iteration, documentation drafts, and hackathon-readiness checks.

## Areas Assisted

- Removing unused 0G/TEE scaffolding and updating tests.
- Implementing and refining the buyer/seller flow around RFQs, quotes, escrow,
  KeeperHub workflows, Uniswap quote proof, and ERC-8004-style registries.
- Drafting and polishing README, submission notes, sponsor feedback, and
  integration guidance.
- Building the local service-backed Agent Bazaar SDK onboarding path used for
  demo validation.

## Human Direction

- The project concept, sponsor-selection strategy, private key management,
  deployed-wallet choices, KeeperHub workflow configuration, and final product
  direction were directed by the team.
- AI-generated code and documents were reviewed, edited, tested, and adjusted
  inside the repository before submission.

## Spec-Driven Development

This project did not use a formal spec-driven framework such as OpenSpec, Kiro,
or spec-kit. The planning process was conversational and team-directed. A
sanitized summary of the team direction and planning artifacts is included in
[`DEVELOPMENT_PROCESS.md`](DEVELOPMENT_PROCESS.md).

## Artifacts

- Source code and tests are in this repository.
- The main implementation history is tracked through Git commits and working
  tree changes during the hackathon.
- Additional process notes are in [`DEVELOPMENT_PROCESS.md`](DEVELOPMENT_PROCESS.md)
  and [`HACKATHON_NOTES.md`](HACKATHON_NOTES.md).
