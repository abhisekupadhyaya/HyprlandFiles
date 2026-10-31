# Security policy

This release candidate has no claim of audited security or universal hardware
support. Use a reviewed tagged release/commit, retain recovery access and keep
Ubuntu security updates enabled. Exact desktop freezes need prompt security
review; report a problem without posting credentials or unredacted host dumps.

For sensitive reports, use GitHub's private vulnerability reporting if enabled
for this repository, or contact the maintainer privately through their public
profile. Do not put exploit details containing credentials into a public issue.
There is no telemetry or built-in diagnostic upload. Review every report before
sharing; usernames, IP addresses and device identifiers may still be personal.

The installer never requests a password in chat/config. Sudo/PAM use local
terminal/native prompts. APT metadata is signed with scoped source keys, Python
wheels and the original greeter package are hash-locked. The nwg-hello privacy
patch must not be dropped: older upstream packaging logged credential payloads.
Private root/user backups and generated state are never repository contents.

Tests are not a substitute for wrong-password, lock-death, TTY recovery and
clean-machine acceptance. No test may bypass authentication, disable firewall,
Secure Boot, OS security updates, or clear failure state just to produce PASS.
