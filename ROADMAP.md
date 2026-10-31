# Roadmap

## First stable release gates

- Clean Ubuntu Server 26.04 amd64 installation from both online source and the
  preserved source-plus-kit archive; verify repeated setup and rollback.
- Physical login / wrong-password / TTY recovery and complete laptop/server
  lifecycle acceptance of the portable paths. Desktop profile acceptance too.
- Confirm portals, authentication agent, audio/keys, cached themes and hardware
  acceleration on actual target machines. Preserve logs of failures.
- Retain the complete release archive off the development machine, run public CI,
  review binary redistribution requirements and configure repository protections.

## Compatibility expansion

Each additional Ubuntu Server release or CPU architecture gets its own reviewed
package/runtime lock, adapter where necessary, clean-machine test and published
support entry. Broader Intel/AMD/NVIDIA/hybrid monitor testing is incremental;
there is no promise that one binary lock supports every historical/future Ubuntu.
Unsupported platforms fail before installation rather than using guessed syntax.

## Maintenance

Versioned migrations must preserve local overrides and original rollback history.
The initial installer is not a live in-session updater. Add an explicit migration
runner only with transactional upgrade, interrupted-run and recovery evidence.
Continue dependency/security review, contributor documentation and release tests.
No network manager replacement, driver wizard, disk installer or boot cosmetics
are implicit roadmap commitments.
