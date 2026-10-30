# Compatibility boundary

| Component/platform | Initial support |
| --- | --- |
| OS / CPU | Ubuntu Server 26.04 / amd64 only; explicitly checked |
| Python | Ubuntu Python 3.14; locked Pillow wheel ABI |
| Hyprland | 0.57.0 from cppiber's signed PPA; exact ABI dependency lock |
| Intel i915 | Original desktop accelerated in real hardware testing |
| Intel xe / AMD | Detection/default selection implemented; clean-machine hardware validation pending |
| NVIDIA / mixed external wiring | Existing driver only; manual renderer/output testing required |
| Desktop without lid | Separate profile, simulated; clean-machine validation pending |
| Laptop/server | Core lifecycle physically exercised before portability work; portable install retest pending |
| arm64, Ubuntu 24.04, other distributions | Refused; contribute a reviewed release/architecture lock and tests |

Being open source means everyone may inspect, adapt and contribute; it does not
mean pretending that one package lock supports every machine. No Radeon, Intel
PCI address, connector name, login account or Wi-Fi interface is hardcoded.

The PPA is third-party software, not an Ubuntu support guarantee. Signed package
availability is checked by APT at installation. If an exact version has been
removed, installation fails; it never chooses another release silently. Store
reviewed signed archives as release artifacts before claiming long-term offline
reproducibility. This repository currently contains source/locks, not a complete
APT mirror. A future machine still needs a maintained compatible release of this
project and normal Ubuntu updates.

A Wayland-capable GPU and local display/input are required for hardware GUI
acceptance. VM tests need an appropriate virtual GPU. Headless-only servers can
inspect plans; they should not install the desktop until their GPU/login path
has been reviewed. Default profile does not suspend or alter power management.
