#!/usr/bin/python3
# SPDX-License-Identifier: MIT
"""hyprlandfilesd: lid-aware greeter control for a headless-first laptop.

Invariants (the reason this file exists):
  * It never starts a graphical session. It only starts/stops the greeter
    unit (greetd.service). greetd authenticates through PAM and opens the
    user's session through logind, as the user.
  * It never stops the greeter unit while an authenticated graphical
    session exists on seat0 (greetd is that session's parent).
  * It acts on the current, debounced lid state, never on an event payload.
  * It never touches SSH, tty or other non-graphical sessions.
  * It powers the internal panel on/off only while the text console owns the
    display (no desktop session, greeter unit down). The kernel ignores
    fbdev blanking while a compositor holds DRM master in any case.
  * All actions happen in one single-threaded loop, so there is no
    concurrent start/stop.
"""
import ctypes, ctypes.util, errno, fcntl, glob, json, logging, os, pwd, select
import signal, socket, struct, subprocess, sys, time
from dataclasses import dataclass, field, replace
from typing import Optional

LOG = logging.getLogger("hyprlandfilesd")

# --------------------------------------------------------------------------
# Pure decision core (unit-tested off-machine)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Config:
    profile: str = "desktop"             # desktop | laptop-server
    greeter_unit: str = "greetd.service"
    greeter_service: str = "greetd"       # PAM service name logind records
    allowed_users: tuple = ()
    settle: float = 1.0                   # lid must hold a state this long
    stop_grace: float = 3.0               # greeter-only + unwanted, this long
    handoff_timeout: float = 20.0         # unit up, no greeter, no user session
    lock_verify: float = 6.0
    docked_policy: str = "strict"         # strict | keep-external
    console_vt: int = 1
    panel_control: bool = True            # console panel follows the lid
    panel_retry: float = 30.0             # resend an unconfirmed panel change
    start_burst: int = 3
    start_window: float = 120.0
    start_backoff: float = 300.0
    idle_tick: float = 30.0
    busy_tick: float = 0.5
    runtime_dir: str = "/run/hyprlandfiles"


@dataclass(frozen=True)
class Session:
    id: str
    user: str = ""
    seat: str = ""
    cls: str = ""        # user | greeter | lock-screen | background | ...
    type: str = ""       # wayland | x11 | tty | unspecified
    service: str = ""    # greetd | sshd | login | ...
    state: str = ""      # online | active | closing
    remote: bool = False
    locked: bool = False


def is_gui_user_session(s: Session, cfg: Config) -> bool:
    if s.remote or s.seat != "seat0" or s.cls != "user":
        return False
    return s.service == cfg.greeter_service or s.type in ("wayland", "x11", "mir")


def is_greeter_session(s: Session, cfg: Config) -> bool:
    # greetd 0.10 uses greetd-greeter for the login screen and greetd for
    # authenticated users. The prior shared name remains compatible.
    return (s.cls == "greeter" and not s.remote and s.state != "closing"
            and s.seat == "seat0"
            and s.service in (cfg.greeter_service, cfg.greeter_service + "-greeter"))


@dataclass
class Observation:
    now: float
    lid: str                     # open | closed | unknown
    unit_state: str              # systemd ActiveState of the greeter unit
    sessions: tuple = ()
    externals: bool = False      # an external display is connected
    suppressed: bool = False     # manual desktop-off in force
    requested: bool = False      # explicit desktop-on while lid not open
    panel: str = "unknown"       # internal panel DPMS: on | off | unknown


@dataclass
class Memory:
    raw_lid: Optional[str] = None
    raw_since: float = 0.0
    stable_lid: Optional[str] = None
    lock_sent: dict = field(default_factory=dict)     # session id -> time
    lock_retried: set = field(default_factory=set)
    stop_candidate_since: Optional[float] = None
    handoff_since: Optional[float] = None
    starts: list = field(default_factory=list)
    backoff_until: float = 0.0
    console_restore_pending: bool = False
    busy_until: float = 0.0
    panel_sent: Optional[str] = None
    panel_at: float = 0.0


@dataclass(frozen=True)
class Action:
    kind: str                 # START STOP LOCK CHVT PANEL CLEAR_SUPPRESSED CLEAR_REQUESTED WARN
    arg: object = None


def greeter_wanted(lid, suppressed, requested, docked):
    return (not suppressed) and (lid == "open" or requested or docked)


def console_panel_target(lid):
    # Powering the panel off on close makes every lid open a full panel
    # power-up. A panel left lit behind a closed lid stayed black when the lid
    # was reopened (Inspiron 7559, 2026-10-30).
    return {"open": "on", "closed": "off"}.get(lid)


def converge_panel(acts, obs, mem, cfg, target):
    if not cfg.panel_control or target is None or obs.panel in (target, "unknown"):
        return
    if mem.panel_sent == target and obs.now - mem.panel_at < cfg.panel_retry:
        return
    acts.append(Action("PANEL", target))
    mem.panel_sent, mem.panel_at = target, obs.now


def decide(obs: Observation, mem: Memory, cfg: Config):
    """Return (actions, greeter_wanted). Mutates mem only."""
    if cfg.profile == "desktop":
        obs = replace(obs, lid="open")
    acts = []
    now = obs.now

    # 1. Debounce: only a lid state held for `settle` seconds counts.
    if obs.lid != mem.raw_lid:
        mem.raw_lid, mem.raw_since = obs.lid, now
    if now - mem.raw_since < cfg.settle:
        return acts, None

    suppressed, requested = obs.suppressed, obs.requested
    if mem.raw_lid != mem.stable_lid:
        prev, mem.stable_lid = mem.stable_lid, mem.raw_lid
        mem.lock_sent.clear()
        mem.lock_retried.clear()
        if prev == "closed" and mem.stable_lid == "open" and suppressed:
            acts.append(Action("CLEAR_SUPPRESSED"))   # genuine close -> open
            suppressed = False
        if prev == "open" and mem.stable_lid == "closed" and requested:
            acts.append(Action("CLEAR_REQUESTED"))
            requested = False
    lid = mem.stable_lid

    docked = cfg.docked_policy == "keep-external" and obs.externals
    gui = [s for s in obs.sessions if is_gui_user_session(s, cfg)]
    greeters = [s for s in obs.sessions if is_greeter_session(s, cfg)]
    want = greeter_wanted(lid, suppressed, requested, docked)

    # 2. An authenticated desktop exists: never stop the greeter unit.
    if gui:
        mem.stop_candidate_since = mem.handoff_since = None
        if lid != "open" and lid != "unknown" and not docked and not requested:
            for s in gui:
                if s.locked:
                    continue
                sent = mem.lock_sent.get(s.id)
                if sent is None:
                    acts.append(Action("LOCK", s.id))
                    mem.lock_sent[s.id] = now
                elif now - sent >= cfg.lock_verify and s.id not in mem.lock_retried:
                    acts.append(Action("WARN", f"session {s.id} not confirmed locked "
                                       f"{cfg.lock_verify:.0f}s after lock request; retrying once"))
                    acts.append(Action("LOCK", s.id))
                    mem.lock_retried.add(s.id)
        return acts, want

    # 3. No desktop. Converge the greeter unit on `want`.
    unit_up = obs.unit_state in ("active", "activating", "reloading")
    if want:
        mem.stop_candidate_since = mem.handoff_since = None
        if obs.unit_state in ("inactive", "failed"):
            if lid == "open":
                converge_panel(acts, obs, mem, cfg, "on")   # before the greeter's modeset
            if now < mem.backoff_until:
                return acts, want
            mem.starts = [t for t in mem.starts if now - t < cfg.start_window]
            if len(mem.starts) >= cfg.start_burst:
                mem.backoff_until = now + cfg.start_backoff
                acts.append(Action("WARN", f"greeter started {cfg.start_burst} times in "
                                   f"{cfg.start_window:.0f}s without a login; backing off "
                                   f"{cfg.start_backoff:.0f}s (check: journalctl -u {cfg.greeter_unit})"))
                return acts, want
            mem.starts.append(now)
            acts.append(Action("START"))
        return acts, want

    if not unit_up:
        mem.stop_candidate_since = mem.handoff_since = None
        if obs.unit_state in ("inactive", "failed"):
            if mem.console_restore_pending:
                acts.append(Action("CHVT", cfg.console_vt))
                mem.console_restore_pending = False
            converge_panel(acts, obs, mem, cfg, console_panel_target(lid))
        return acts, want

    if greeters:
        mem.handoff_since = None
        if mem.stop_candidate_since is None:
            mem.stop_candidate_since = now
        elif now - mem.stop_candidate_since >= cfg.stop_grace:
            acts.append(Action("STOP"))
            mem.stop_candidate_since = None
            mem.console_restore_pending = True
    else:
        # Unit up but neither a greeter nor a user session: the greeter is
        # starting, or a just-authenticated session is being created. Wait.
        mem.stop_candidate_since = None
        if mem.handoff_since is None:
            mem.handoff_since = now
        elif now - mem.handoff_since >= cfg.handoff_timeout:
            acts.append(Action("WARN", "greeter unit up with neither a greeter nor a "
                               "user session for too long; stopping it"))
            acts.append(Action("STOP"))
            mem.handoff_since = None
            mem.console_restore_pending = True
    return acts, want


def stop_still_safe(obs: Observation, cfg: Config) -> bool:
    """Re-check with a fresh observation immediately before stopping greetd."""
    return not any(is_gui_user_session(s, cfg) for s in obs.sessions)


def is_busy(obs: Observation, mem: Memory, cfg: Config) -> bool:
    return (obs.lid != mem.stable_lid or mem.stop_candidate_since is not None
            or mem.handoff_since is not None or any(
                obs.now - sent < cfg.lock_verify + 2 and sid not in mem.lock_retried
                for sid, sent in mem.lock_sent.items()) or obs.now < mem.busy_until
            or obs.unit_state in ("activating", "deactivating", "reloading"))


# --------------------------------------------------------------------------
# Observation sources (Linux only)
# --------------------------------------------------------------------------

def _ioc_read(nr, size, typ=ord("E")):
    return (2 << 30) | (size << 16) | (typ << 8) | nr

EVIOCGSW = _ioc_read(0x1B, 8)
SW_LID = 0


class LidSource:
    """Reads the lid switch via evdev (no grab), falling back to ACPI procfs."""

    def __init__(self):
        self.fd = None
        self.path = None
        for ev in sorted(glob.glob("/sys/class/input/event*")):
            try:
                name = open(f"{ev}/device/name").read().strip()
                sw = int(open(f"{ev}/device/capabilities/sw").read().split()[-1], 16)
            except (OSError, ValueError, IndexError):
                continue
            if name == "Lid Switch" and sw & (1 << SW_LID):
                path = "/dev/input/" + os.path.basename(ev)
                try:
                    self.fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
                    self.path = path
                    break
                except OSError as e:
                    LOG.warning("cannot open %s: %s", path, e)
        LOG.info("lid source: %s", self.path or "procfs fallback")

    def drain(self):
        if self.fd is None:
            return
        try:
            while os.read(self.fd, 4096):
                pass
        except BlockingIOError:
            pass

    def state(self):
        if self.fd is not None:
            buf = bytearray(8)
            try:
                fcntl.ioctl(self.fd, EVIOCGSW, buf, True)
                return "closed" if buf[0] & (1 << SW_LID) else "open"
            except OSError as e:
                LOG.warning("EVIOCGSW failed: %s", e)
        for p in glob.glob("/proc/acpi/button/lid/*/state"):
            try:
                txt = open(p).read()
            except OSError:
                continue
            if "closed" in txt:
                return "closed"
            if "open" in txt:
                return "open"
        return "unknown"


class Inotify:
    IN_CLOSE_WRITE, IN_MOVED_TO, IN_CREATE, IN_DELETE = 0x8, 0x80, 0x100, 0x200

    def __init__(self, path):
        self.fd = None
        libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6", use_errno=True)
        fd = libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
        if fd < 0:
            return
        mask = self.IN_CLOSE_WRITE | self.IN_MOVED_TO | self.IN_CREATE | self.IN_DELETE
        if libc.inotify_add_watch(fd, path.encode(), mask) < 0:
            os.close(fd)
            return
        self.fd = fd

    def drain(self):
        try:
            while os.read(self.fd, 65536):
                pass
        except BlockingIOError:
            pass


def _run(argv, timeout=10):
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout)


PROPS = ["Id", "Name", "Seat", "Class", "Type", "Service", "State", "Remote", "LockedHint"]


def read_sessions():
    r = _run(["loginctl", "list-sessions", "--no-legend", "--no-pager"])
    if r.returncode:
        raise RuntimeError("logind session enumeration failed; refusing lifecycle actions")
    ids = [ln.split()[0] for ln in r.stdout.splitlines() if ln.strip()]
    if not ids:
        return ()
    argv = ["loginctl", "show-session", "--no-pager"] + ids
    for p in PROPS:
        argv += ["-p", p]
    r = _run(argv)
    if r.returncode:
        raise RuntimeError("logind session properties failed; refusing lifecycle actions")
    out, cur = [], {}
    for ln in (r.stdout + "\n").splitlines():
        if not ln.strip():
            if cur.get("Id"):
                out.append(Session(id=cur["Id"], user=cur.get("Name", ""),
                                   seat=cur.get("Seat", ""), cls=cur.get("Class", ""),
                                   type=cur.get("Type", ""), service=cur.get("Service", ""),
                                   state=cur.get("State", ""), remote=cur.get("Remote") == "yes",
                                   locked=cur.get("LockedHint") == "yes"))
            cur = {}
            continue
        k, _, v = ln.partition("=")
        cur[k] = v
    return tuple(out)


def unit_state(unit):
    r = _run(["systemctl", "show", "-p", "ActiveState", "--value", unit])
    return r.stdout.strip() or "unknown"


def externals_connected():
    for st in glob.glob("/sys/class/drm/card*-*/status"):
        conn = os.path.basename(os.path.dirname(st)).split("-", 1)[-1]
        if conn.startswith(("eDP", "LVDS", "DSI", "Writeback")):
            continue
        try:
            if open(st).read().strip() == "connected":
                return True
        except OSError:
            pass
    return False


class Panel:
    """The internal panel as the text console sees it: the connector's DPMS
    state, switched through the fbdev blank control of the same card."""

    def __init__(self):
        self.dpms = self.blank = None
        for st in sorted(glob.glob("/sys/class/drm/card*-*/status")):
            conn = os.path.dirname(st)
            card, _, name = os.path.basename(conn).partition("-")
            if not name.startswith(("eDP", "LVDS", "DSI")):
                continue
            try:
                if open(st).read().strip() != "connected":
                    continue
            except OSError:
                continue
            dev = os.path.realpath(f"/sys/class/drm/{card}/device")
            for fb in sorted(glob.glob("/sys/class/graphics/fb[0-9]*")):
                if os.path.realpath(f"{fb}/device") == dev:
                    self.dpms, self.blank = f"{conn}/dpms", f"{fb}/blank"
                    break
            if self.dpms:
                break
        LOG.info("internal panel: %s via %s", self.dpms or "not found", self.blank or "-")

    def state(self):
        if not self.dpms:
            return "unknown"
        try:
            return "on" if open(self.dpms).read().strip() == "On" else "off"
        except OSError:
            return "unknown"

    def set(self, target):
        with open(self.blank, "w") as f:
            f.write("0" if target == "on" else "4")   # FB_BLANK_UNBLANK / _POWERDOWN


# --------------------------------------------------------------------------
# Daemon
# --------------------------------------------------------------------------

def load_config(path="/etc/hyprlandfiles/hyprlandfiles.conf") -> Config:
    kv = {}
    try:
        for ln in open(path):
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1)
                kv[k.strip().lower()] = v.strip().strip('"')
    except FileNotFoundError:
        pass
    base = Config()
    conv = {}
    for k, v in kv.items():
        if not hasattr(base, k):
            LOG.warning("unknown config key %s ignored", k)
            continue
        cur = getattr(base, k)
        if isinstance(cur, bool):
            conv[k] = v.lower() in ("1", "yes", "true")
        elif isinstance(cur, int):
            conv[k] = int(v)
        elif isinstance(cur, float):
            conv[k] = float(v)
        elif isinstance(cur, tuple):
            conv[k] = tuple(x for x in v.replace(",", " ").split() if x)
        else:
            conv[k] = v
    cfg = Config(**{**base.__dict__, **conv})
    if cfg.profile not in ("desktop", "laptop-server"):
        raise ValueError("Invalid profile")
    if cfg.docked_policy not in ("strict", "keep-external"):
        raise SystemExit(f"bad docked_policy {cfg.docked_policy!r}")
    return cfg


def sd_notify(msg):
    addr = os.environ.get("NOTIFY_SOCKET")
    if not addr:
        return
    if addr.startswith("@"):
        addr = "\0" + addr[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM | socket.SOCK_CLOEXEC) as s:
            s.connect(addr)
            s.sendall(msg.encode())
    except OSError:
        pass


class Daemon:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.rd = cfg.runtime_dir
        self.mem = Memory()
        self.last = {}
        self.allowed_uids = {0}
        self.sock_gid = 0
        for u in cfg.allowed_users:
            try:
                pw = pwd.getpwnam(u)
                self.allowed_uids.add(pw.pw_uid)
                self.sock_gid = self.sock_gid or pw.pw_gid
            except KeyError:
                LOG.warning("allowed user %s does not exist", u)
        os.makedirs(self.rd, mode=0o755, exist_ok=True)
        self.lid = LidSource()
        self.panel = Panel() if cfg.panel_control else None
        self.ino = Inotify("/run/systemd/sessions")
        self.sock = self._listen()
        # Every managed desktop holds a shared lock BEFORE starting applications.
        # STOP takes the exclusive lock through completion of greetd shutdown.
        # A fresh logind query alone cannot close the PAM/session-start race.
        self.guard = os.open(os.path.join(self.rd, "session.guard"),
                             os.O_CREAT | os.O_RDWR | os.O_CLOEXEC, 0o644)
        os.fchmod(self.guard, 0o644)
        self.stop = False

    # flags --------------------------------------------------------------
    def _flag(self, name):
        return os.path.exists(os.path.join(self.rd, name))

    def _set_flag(self, name, on):
        p = os.path.join(self.rd, name)
        if on:
            with open(p, "w") as f:
                f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')}\n")
            os.chmod(p, 0o644)
        else:
            try:
                os.unlink(p)
            except FileNotFoundError:
                pass

    # observation --------------------------------------------------------
    def observe(self) -> Observation:
        return Observation(now=time.monotonic(), lid=(self.lid.state() if self.cfg.profile == "laptop-server" else "open"),
                           unit_state=unit_state(self.cfg.greeter_unit),
                           sessions=read_sessions(),
                           externals=externals_connected(),
                           suppressed=self._flag("suppressed"),
                           requested=self._flag("requested"),
                           panel=self.panel.state() if self.panel else "unknown")

    # actions ------------------------------------------------------------
    def execute(self, acts):
        for a in acts:
            if a.kind == "WARN":
                LOG.warning("%s", a.arg)
            elif a.kind == "CLEAR_SUPPRESSED":
                LOG.info("lid closed -> open: clearing manual desktop-off")
                self._set_flag("suppressed", False)
            elif a.kind == "CLEAR_REQUESTED":
                LOG.info("lid open -> closed: clearing explicit desktop-on request")
                self._set_flag("requested", False)
            elif a.kind == "START":
                LOG.info("starting %s", self.cfg.greeter_unit)
                _run(["systemctl", "start", "--no-block", self.cfg.greeter_unit])
                self.mem.busy_until = time.monotonic() + 15
            elif a.kind == "STOP":
                try:
                    fcntl.flock(self.guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    LOG.info("stop aborted: a managed desktop holds the session guard")
                    continue
                try:
                    fresh = self.observe()
                    if not stop_still_safe(fresh, self.cfg):
                        LOG.info("stop aborted: an authenticated session appeared")
                        self.mem.console_restore_pending = False
                        continue
                    LOG.info("stopping %s (session guard held; no desktop)", self.cfg.greeter_unit)
                    r = _run(["systemctl", "stop", self.cfg.greeter_unit], timeout=45)
                    if r.returncode:
                        raise RuntimeError("greetd stop failed: " + r.stderr.strip())
                finally:
                    fcntl.flock(self.guard, fcntl.LOCK_UN)
                self.mem.busy_until = time.monotonic() + 15
            elif a.kind == "LOCK":
                LOG.info("lid closed with desktop session %s: locking", a.arg)
                r = _run(["loginctl", "lock-session", str(a.arg)])
                if r.returncode != 0:
                    LOG.error("lock-session %s failed: %s", a.arg, r.stderr.strip())
                self.mem.busy_until = time.monotonic() + self.cfg.lock_verify + 2
            elif a.kind == "CHVT":
                _run(["chvt", str(a.arg)])
            elif a.kind == "PANEL":
                try:
                    self.panel.set(a.arg)
                except OSError as e:
                    LOG.error("panel %s failed: %s", a.arg, e)
                    continue
                now = self.panel.state()
                LOG.info("console panel %s (lid %s)%s", a.arg, self.mem.stable_lid,
                         "" if now == a.arg else f"; still {now}, a compositor holds the display")

    def publish(self, obs, want):
        gui = [s for s in obs.sessions if is_gui_user_session(s, self.cfg)]
        st = {"lid": self.mem.stable_lid or obs.lid, "greeter_unit": obs.unit_state,
              "desktop_sessions": [{"id": s.id, "user": s.user, "locked": s.locked} for s in gui],
              "greeter_sessions": [s.id for s in obs.sessions if is_greeter_session(s, self.cfg)],
              "suppressed": obs.suppressed, "requested": obs.requested,
              "externals": obs.externals, "panel": obs.panel,
              "docked_policy": self.cfg.docked_policy,
              "greeter_wanted": want}
        self.last = st
        tmp = os.path.join(self.rd, ".status.json")
        with open(tmp, "w") as f:
            json.dump(st, f)
        os.chmod(tmp, 0o644)
        os.replace(tmp, os.path.join(self.rd, "status.json"))

    # control socket -------------------------------------------------------
    def _listen(self):
        p = os.path.join(self.rd, "control.sock")
        try:
            os.unlink(p)
        except FileNotFoundError:
            pass
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM | socket.SOCK_CLOEXEC)
        s.bind(p)
        os.chown(p, 0, self.sock_gid)
        os.chmod(p, 0o660)
        s.listen(4)
        s.setblocking(False)
        return s

    def handle_client(self):
        try:
            c, _ = self.sock.accept()
        except BlockingIOError:
            return
        with c:
            c.settimeout(5)
            pid, uid, gid = struct.unpack("3i", c.getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))
            if uid not in self.allowed_uids:
                LOG.warning("rejected control request from uid %d (pid %d)", uid, pid)
                c.sendall(b'{"ok": false, "error": "not authorised"}\n')
                return
            try:
                line = c.recv(256).decode(errors="replace").strip()
            except OSError:
                return
            reply = self.command(line, uid)
            c.sendall((json.dumps(reply) + "\n").encode())

    def command(self, line, uid):
        parts = line.split()
        cmd = parts[0] if parts else ""
        obs = self.observe()
        gui = [s for s in obs.sessions if is_gui_user_session(s, self.cfg)]
        if cmd == "status":
            return {"ok": True, **self.last}
        if cmd == "on":
            LOG.info("desktop-on requested by uid %d", uid)
            self._set_flag("suppressed", False)
            lid_open = (self.mem.stable_lid or obs.lid) == "open"
            self._set_flag("requested", not lid_open)
            return {"ok": True, "lid": self.mem.stable_lid or obs.lid,
                    "desktop_sessions": [s.id for s in gui],
                    "externals": obs.externals}
        if cmd == "off":
            LOG.info("desktop-off requested by uid %d", uid)
            self._set_flag("requested", False)
            self._set_flag("suppressed", True)
            return {"ok": True, "desktop_sessions": [s.id for s in gui]}
        return {"ok": False, "error": f"unknown command {line!r}"}

    # loop -------------------------------------------------------------------
    def run(self):
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, "stop", True))
        signal.signal(signal.SIGINT, lambda *_: setattr(self, "stop", True))
        sd_notify("READY=1")
        LOG.info("started: greeter=%s docked_policy=%s allowed=%s", self.cfg.greeter_unit,
                 self.cfg.docked_policy, ",".join(self.cfg.allowed_users) or "root")
        fds = [self.sock]
        if self.lid.fd is not None:
            fds.append(self.lid.fd)
        if self.ino.fd is not None:
            fds.append(self.ino.fd)
        while not self.stop:
            try:
                obs = self.observe()
                acts, want = decide(obs, self.mem, self.cfg)
                if want is not None:   # before START, so the greeter wrapper sees it
                    self._set_flag("greeter-wanted", want)
                self.execute(acts)
                self.publish(obs, want)
                timeout = self.cfg.busy_tick if is_busy(obs, self.mem, self.cfg) else self.cfg.idle_tick
            except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
                LOG.error("lifecycle observation/action failed (no further action this cycle): %s", exc)
                timeout = self.cfg.idle_tick
            sd_notify("WATCHDOG=1")
            try:
                ready, _, _ = select.select(fds, [], [], timeout)
            except InterruptedError:
                continue
            for r in ready:
                if r is self.sock:
                    self.handle_client()
                elif r == self.lid.fd:
                    self.lid.drain()
                elif r == self.ino.fd:
                    self.ino.drain()
        try:
            os.unlink(os.path.join(self.rd, "control.sock"))
        except FileNotFoundError:
            pass
        LOG.info("stopped")


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stdout)
    if os.geteuid() != 0:
        raise SystemExit("hyprlandfilesd must run as root (systemd service)")
    Daemon(load_config()).run()


if __name__ == "__main__":
    main()
