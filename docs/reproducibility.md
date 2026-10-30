# Recreate this workstation later

The user-facing goal is Ubuntu Server, an existing local account, the project,
and **one installer command**. Hardware/account detection replaces private host
settings. A retained source-plus-kit release additionally removes dependence on
old desktop binaries remaining online. You do not repeat the original manual
configuration work or build the compositor yourself.

## Normal fresh installation

```sh
git clone https://github.com/abhisekupadhyaya/HyprlandFiles.git
cd HyprlandFiles
./install.sh
```

The default profile is automatic: readable ACPI lid hardware selects the
laptop/server contract; otherwise desktop. The plan prints its choice. Explicit
profile/scale/keyboard/GPU options remain available. Sudo and confirmation are
still required; a reboot remains the operator's saved-work decision.

The current implementation supports Ubuntu Server 26.04 amd64. A new Ubuntu
release has different package/Python ABIs and needs a tested project release.
A one-command interface cannot safely turn a 26.04 lock into support for every
past/future Ubuntu release. Unsupported systems stop before system changes.

## Retain a source-plus-kit release

A source-plus-kit `.tar.gz` contains the reviewed portable source and
`HyprlandFiles/bundles/ubuntu-26.04-amd64`. After extraction:

```sh
cd HyprlandFiles
./install.sh verify-bundle
./install.sh
```

The conventional bundle location is detected automatically. A standalone kit can
be supplied with `--bundle /path/to/kit`. Verification checks **every** artifact
against the manifest in the reviewed source checkout, plus .deb package/version/
architecture identities. The kit's own manifest cannot authorize changed bytes.
Tampered, missing, redirected or stale kits are refused before installation.

The 33 artifacts are 28 exact desktop packages, the patched nwg-hello package,
its original Ubuntu build input, and three locked Python wheels. Install uses
prebuilt verified desktop packages; it skips the greeter build and does not add
the PPA on a fresh machine. Normal Ubuntu dependencies still come from signed
Ubuntu repositories, and ordinary security updates remain enabled. It is not a
complete offline OS mirror and does not freeze shared OS/security libraries.

Keep the archive in a separate backup location. Git contains the small trust
manifest, not the 75 MB binary kit. An unpushed local repository or one copy on a
laptop is not a durable backup. A public source-only clone still uses the online
package path until a reviewed kit/release archive is separately distributed.
Publishing to GitHub or uploading binary release assets is an explicit maintainer
action, never performed by this installer.

## Maintainer preparation

While signed APT indexes still provide the release versions, obtain their
archives with `apt-get download PACKAGE=VERSION` (no installation/root needed).
Prepare the original greeter input, build the reviewed patched package with
`python3 tools/build_greeter.py`, and obtain the locked wheels with
`python3 tools/prepare_dev.py`. Existing verified caches may be reused.

```sh
python3 tools/recovery.py create /new/kit-directory \
  --archive-dir /path/to/debs --archive-dir .cache --write-manifest
python3 tools/recovery.py verify /new/kit-directory
python3 tools/recovery.py package /new/kit-directory dist/HyprlandFiles-release.tar.gz
```

`--write-manifest` is a deliberate **release-maintainer** operation, not an
end-user repair switch. The builder verifies original .deb hashes against local
signed APT metadata, verifies the original greeter/wheel hashes, and checks the
patched package against its reproducible-build record before writing a new Git
manifest. Review and commit that manifest. Without this flag, create must match
the existing manifest exactly. Destinations must be new; known-good artifacts
are never overwritten. Packaging excludes Git metadata, caches, local bundles,
private backups and reports; tar/gzip metadata is normalized for reproducibility.

Before publishing binary artifacts, preserve upstream package licences and meet
applicable source-distribution obligations described in THIRD_PARTY_NOTICES.md.
Archive extraction, kit verification and safe plan checks are automated; fresh
installation and physical authentication/lifecycle tests remain separate release
gates. An archive's existence alone does not prove clean-machine acceptance.
