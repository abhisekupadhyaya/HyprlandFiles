# Release and maintenance policy

## Versioned user contract

VERSION and the installer version must agree. Use `MAJOR.MINOR.PATCH`; pre-release
suffixes such as `-rc.1` identify candidates. A major release changes a supported
installation/configuration contract incompatibly. Minor releases add reviewed
features or platform support; patches fix compatible behaviour. An RC is not a
claim of production acceptance. Support is defined by docs/compatibility.md and
actual test evidence, not by a version label alone.

Version package/runtime locks with the source that consumes them. Updates must
preserve existing palettes, user.lua, unrelated edits and backup history. No
installer silently follows an upstream branch or substitutes a new desktop ABI.
Before changing an already installed release, publish an explicit migration and
rollback procedure. The current installer intentionally refuses active GUIs and
profile migrations; `git pull && sudo install` is not a supported live updater.

## Release candidate preparation

1. Use a feature branch/PR. Review root, login and source-trust changes and
   third-party notices. Update CHANGELOG, VERSION and relevant migration docs.
2. Run isolated checks, extended palette tests, native parser/unit checks and two
   greeter builds. Verify package/wheel locks and kit hashes. Generate the release
   input SBOM with `python3 tools/sbom.py --check` (or regenerate after manifest
   changes). This inventory covers retained inputs, not every target OS package.
3. On a disposable clean Ubuntu Server installation, test the online installer,
   kit installer, repeated setup, conflicts, interrupted-stage recovery and
   complete rollback. Do not run destructive acceptance on a contributor's
   working desktop merely to satisfy CI.
4. Perform docs/acceptance.md on supported hardware with explicit saved-work and
   recovery access for disruptive tests. Record OS/architecture/GPU classes and
   observed results without publishing private host inventory. Mark untested
   cases and failures explicitly.
5. Build the source-plus-kit archive, verify a fresh extraction against its Git
   manifest, and retain it separately. Produce SHA256SUMS for distribution and
   review upstream binary/source redistribution obligations. Sign release tags /
   artifacts when a maintainer-controlled signing identity is configured; never
   invent a key or mark an unsigned build signed.
6. Obtain maintainer approval, tag the reviewed commit, publish release notes,
   compatibility/limitations and approved artifacts. Publishing, uploading and
   making a repository public are explicit owner actions. CI here neither pushes
   commits nor publishes releases automatically.

## Public launch and project health

Keep README install/recovery instructions, contributor guidance, issue/PR
forms, code of conduct, license/attribution, security route and changelog current.
Configure required CI/review rules and private vulnerability reporting on the
hosting service; files in Git alone cannot enable those settings. Do not use fake
passing badges, invented support guarantees or stock screenshots as test evidence.

Review desktop security advisories promptly and package locks at least monthly.
OS security updates stay enabled. Fix a security issue in a reviewed release;
announce affected versions and recovery with enough detail to act, preserving
reporter privacy. Retire a target explicitly when it can no longer be maintained.

## References considered

The public Omarchy repository's separation of runtime commands, configuration,
installation, migrations, tests and manual is a useful reference:
https://github.com/omacom/omarchy . Its platform/installation assumptions are not
this project's Ubuntu policy. HyprlandFiles remains independently implemented,
with sources and licensing documented in THIRD_PARTY_NOTICES.md.
