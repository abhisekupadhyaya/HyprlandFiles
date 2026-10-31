# Login and server lifecycle

The existing maintained components do the work: greetd/PAM/logind authenticate,
labwc hosts the nwg-hello login frontend, start-hyprland manages the desktop's
native systemd lifecycle, and hyprlock supplies ext-session-lock. The small
controller coordinates lid state and greetd availability; it never authenticates
users or starts Hyprland itself. No autologin or SSH shell hook exists.

For `desktop`, the controller treats the machine as always open. For
`laptop-server`, it reads initial lid state using evdev plus ACPI fallback and
reconciles events, so closed boot and open-after-boot are both handled. Unknown
lid readings do not trigger login. A one-second debounce handles switch bounce;
steady state waits for events with a bounded 30-second reconciliation, with
shorter bounded waits only during transitions. Failed reads refuse actions;
failures are logged. Greeter retries have a burst limit/backoff, not an infinite
restart loop. The controller service is independent of network/server units.

Authenticated seat0 graphical sessions are always preserved. A shared session
supervisor lock versus the controller's exclusive stop lock closes the login /
stop race; logind is queried again before stop. Only the supervisor retains its
lock descriptors, never GUI applications. A private singleton prevents duplicate
managed desktops. Remote/TTY shells cannot invoke the session supervisor to
launch a GUI. The greeter's private D-Bus environment does not leak into the
user manager. Labwc's native `-S` mode ties its lifetime to the login client.

Closing an existing desktop requests real hyprlock and turns off only detected
internal connectors. The locker mirrors **confirmed** lock/unlock into logind;
it never clears LockedHint after a crash. One bounded locker recovery is allowed;
the compositor lock remains engaged if recovery fails. Opening without reboot
turns the display on, then requires authentication to the same session. Closing
a desktop keeps its applications/RAM; it is different from clean headless boot.

On normal desktop shutdown, a synchronous native Hyprland Lua shutdown event
stops only the known graphical helper units before Wayland disappears. PipeWire
units are bound to the graphical-session target. Native user targets stop them
at logout; a plain SSH login does not activate desktop audio. No failure reset,
force-app-kill or success-exit-code masking is used.

`hf-desktop status` inspects; `hf-desktop off` from inside the desktop requests
normal graceful logout and suppresses the login; `hf-desktop on` from TTY/SSH
shows login. Server mode requires saved work because it closes apps. A true
close/open cycle clears manual suppression only in the laptop profile. Desktop
profile users restore login with `hf-desktop on`.

The laptop profile writes a separate logind lid-ignore drop-in. It does not
change other sleep policy, boot target, SSH, network or firewall. On battery the
server remains awake too. A physical battery review and an operator-defined
low-battery policy are necessary; no destructive drain test is supplied.

Native TTY switching in labwc remains available. Default terminal/menu shortcuts
are suppressed with explicit None placeholders (an empty binding list would
load upstream defaults). Power/sleep controls in the unauthenticated chooser are
hidden and disabled; real power actions use the authenticated desktop menu.
User wallpaper changes never execute privileged hooks or change PAM policy.
