"""Runtime hardware selection; reads sysfs, never configures a driver or network."""
import json
import os
from pathlib import Path
import re


def settings():
    p = Path('/etc/hyprlandfiles/session.json')
    return json.loads(p.read_text()) if p.is_file() else {'profile':'desktop','gpu':'auto','scale':'auto'}


def gpu_device(selection='auto', sysfs=Path('/sys/class/drm'), dev=Path('/dev/dri')):
    if selection == 'default':
        return None
    devices = []
    for card in sysfs.glob('card[0-9]*'):
        if not re.fullmatch(r'card\d+', card.name):
            continue
        device = card / 'device'
        try:
            vendor = (device / 'vendor').read_text().strip()
            pci = device.resolve().name
            driver = (device / 'driver').resolve().name
            node = dev / card.name
            if not node.exists():
                continue
            devices.append((pci, vendor, driver, str(node)))
        except OSError:
            continue
    if selection != 'auto':
        match = next((x[3] for x in devices if x[0] == selection), None)
        if not match:
            raise ValueError('Configured GPU is not present: ' + selection)
        return match
    # Integrated Intel first. Otherwise let the compositor select; do not
    # accidentally force a discrete AMD/NVIDIA card in an unknown hybrid system.
    return next((x[3] for x in devices if x[1] == '0x8086' and x[2] in ('i915','xe')), None)


def lid_state(proc=Path('/proc/acpi/button/lid')):
    states = []
    for p in proc.glob('*/state'):
        try:
            text = p.read_text()
        except OSError:
            continue
        if 'closed' in text:
            states.append('closed')
        elif 'open' in text:
            states.append('open')
    if 'closed' in states:
        return 'closed'
    return 'open' if states else 'unknown'


def internal(name):
    return bool(re.fullmatch(r'(eDP|LVDS|DSI)-\d+', name))


def output_scale(output, requested='auto'):
    if requested != 'auto':
        return float(requested)
    current = next((m for m in output.get('modes', []) if m.get('current')), {})
    size = output.get('physical_size', {})
    width = size.get('width', 0) if isinstance(size, dict) else 0
    pixels = current.get('width', 0)
    if width:
        dpi = pixels * 25.4 / width
        return 2.0 if dpi >= 180 else 1.0
    return 2.0 if internal(output['name']) and pixels >= 3200 else 1.0


def backlight(sysfs=Path('/sys/class/backlight')):
    devices = [p for p in sysfs.iterdir() if (p/'max_brightness').is_file()]
    if not devices:
        raise ValueError('No backlight device; external monitor brightness is not configured')
    if len(devices) > 1:
        # Prefer native firmware/driver backlight over duplicated acpi_video.
        native = [p for p in devices if not p.name.startswith('acpi_video')]
        if len(native) == 1:
            return native[0]
        raise ValueError('Multiple backlights; set backlight_device in ~/.config/hyprlandfiles/settings.json')
    return devices[0]
