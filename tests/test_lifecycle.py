"""Scenario tests for the hyprlandfilesd decision core (run: python3 -m unittest)."""
import unittest
from dataclasses import replace
from desktopd import (Config, Memory, Observation, Session, decide,
                           stop_still_safe, is_greeter_session)

CFG = Config(profile="laptop-server",allowed_users=("alice",))
GREETER = lambda i="g1": Session(i, "greeter", "seat0", "greeter", "wayland", "greetd", "online")
DESKTOP = lambda i="5", locked=False: Session(i, "alice", "seat0", "user", "wayland",
                                             "greetd", "active", False, locked)
SSH = Session("9", "alice", "", "user", "tty", "sshd", "active", True)


class DesktopProfile(unittest.TestCase):
    def test_login_without_lid_hardware(self):
        cfg=replace(CFG,profile='desktop');mem=Memory()
        decide(Observation(0,'unknown','inactive'),mem,cfg)
        actions,wanted=decide(Observation(2,'unknown','inactive'),mem,cfg)
        self.assertTrue(wanted)
        self.assertIn('START',[x.kind for x in actions])

    def test_desktop_profile_does_not_apply_laptop_lock_policy(self):
        cfg=replace(CFG,profile='desktop');mem=Memory()
        decide(Observation(0,'closed','active',(DESKTOP(),)),mem,cfg)
        actions,wanted=decide(Observation(2,'closed','active',(DESKTOP(),)),mem,cfg)
        self.assertNotIn('LOCK',[x.kind for x in actions])


class World:
    """Tiny simulator: greetd unit, logind sessions, lid, flags, clock."""

    def __init__(self, lid="closed", cfg=CFG, panel="unknown"):
        self.cfg, self.mem, self.t = cfg, Memory(), 0.0
        self.lid, self.unit = lid, "inactive"
        self.panel, self.panel_works = panel, True  # "unknown" = not modelled
        self.sessions = [SSH]                       # an SSH login is always present
        self.suppressed = self.requested = False
        self.externals = False
        self.log = []                               # (time, action kind, arg)
        self.pending = []                           # (due time, fn)
        self.lock_works = True
        self.before_stop = None                     # hook: state change racing a STOP
        self.login_delay = 0.8

    def obs(self):
        return Observation(self.t, self.lid, self.unit, tuple(self.sessions),
                           self.externals, self.suppressed, self.requested, self.panel)

    def relight(self):
        """A compositor starting or fbcon restoring its mode turns the panel on."""
        if self.panel != "unknown":
            self.panel = "on"

    def later(self, dt, fn):
        self.pending.append((self.t + dt, fn))

    def apply(self, a):
        self.log.append((round(self.t, 2), a.kind, a.arg))
        if a.kind == "START":
            self.unit = "activating"
            self.later(0.3, lambda: (setattr(self, "unit", "active"), self.relight()))
            self.later(1.0, lambda: self.sessions.append(GREETER()) if self.unit == "active" else None)
        elif a.kind == "STOP":
            if self.before_stop:
                self.before_stop(); self.before_stop = None
            if not stop_still_safe(self.obs(), self.cfg):
                self.log.append((self.t, "STOP_ABORTED", None))
                return
            self.unit = "deactivating"
            def done():
                self.unit = "inactive"
                self.sessions = [s for s in self.sessions if s.service != "greetd"]
                self.relight()
            self.later(0.5, done)
        elif a.kind == "LOCK":
            if self.lock_works:
                self.later(0.5, lambda: self.sessions.__setitem__(
                    *next((i, replace(s, locked=True)) for i, s in enumerate(self.sessions)
                          if s.id == a.arg)))
        elif a.kind == "PANEL":
            if self.panel_works:
                self.panel = a.arg
        elif a.kind == "CLEAR_SUPPRESSED":
            self.suppressed = False
        elif a.kind == "CLEAR_REQUESTED":
            self.requested = False

    def run(self, seconds, step=0.25):
        end = self.t + seconds
        while self.t < end - 1e-9:
            self.t = round(self.t + step, 4)
            due = [p for p in self.pending if p[0] <= self.t]
            self.pending = [p for p in self.pending if p[0] > self.t]
            for _, fn in due:
                fn()
            acts, _ = decide(self.obs(), self.mem, self.cfg)
            for a in acts:
                self.apply(a)
        return self

    # user actions
    def login(self):
        """Greeter authenticates: greeter session ends, desktop session appears."""
        self.sessions = [s for s in self.sessions if s.cls != "greeter"]
        self.later(self.login_delay, lambda: self.sessions.append(DESKTOP()))

    def logout(self):
        self.sessions = [s for s in self.sessions if s.cls != "user" or s.service != "greetd"]
        if self.unit == "active":                   # greetd respawns its greeter
            self.later(0.5, lambda: self.sessions.append(GREETER("g2")))

    def kinds(self, kind):
        return [e for e in self.log if e[1] == kind]

    def panel_log(self):
        return [e[2] for e in self.kinds("PANEL")]

    def has_greeter(self):
        return any(s.cls == "greeter" for s in self.sessions)

    def has_desktop(self):
        return any(s.cls == "user" and s.service == "greetd" for s in self.sessions)


class Lifecycle(unittest.TestCase):
    def test_native_greetd_greeter_uses_normal_stop_grace(self):
        greeter=Session('46','_greetd','seat0','greeter','tty','greetd-greeter','active')
        self.assertTrue(is_greeter_session(greeter,CFG))
        self.assertFalse(is_greeter_session(replace(greeter,remote=True),CFG))
        self.assertFalse(is_greeter_session(replace(greeter,seat=''),CFG))
        mem=Memory(raw_lid='open',stable_lid='open')
        def observation(t):return Observation(t,'open','active',(greeter,SSH),suppressed=True)
        first,_=decide(observation(10),mem,CFG)
        second,_=decide(observation(10+CFG.stop_grace),mem,CFG)
        self.assertNotIn('STOP',[a.kind for a in first])
        self.assertIn('STOP',[a.kind for a in second])
        self.assertNotIn('WARN',[a.kind for a in second])

    def test_A_boot_lid_closed_is_pure_server(self):
        w = World("closed").run(120)
        self.assertEqual(w.kinds("START"), [])
        self.assertEqual(w.unit, "inactive")

    def test_B_boot_lid_open_presents_greeter(self):
        w = World("open").run(5)
        self.assertEqual(len(w.kinds("START")), 1)
        self.assertTrue(w.has_greeter())

    def test_C_open_after_headless_boot(self):
        w = World("closed").run(30)
        w.lid = "open"
        w.run(5)
        self.assertEqual(len(w.kinds("START")), 1)
        self.assertTrue(w.has_greeter())

    def test_D_close_during_desktop_locks_and_keeps_session(self):
        w = World("open").run(5)
        w.login(); w.run(3)
        self.assertTrue(w.has_desktop())
        w.lid = "closed"; w.run(60)
        self.assertEqual(len(w.kinds("LOCK")), 1)
        self.assertEqual(w.kinds("STOP"), [])
        self.assertTrue(w.has_desktop())
        self.assertIn(SSH, w.sessions)
        # reopen: no new greeter, same session, no further lock
        w.lid = "open"; w.run(10)
        self.assertEqual(len(w.kinds("START")), 1)
        self.assertEqual(len(w.kinds("LOCK")), 1)
        self.assertTrue(w.has_desktop())

    def test_D_lock_failure_is_retried_once_and_reported(self):
        w = World("open").run(5)
        w.login(); w.run(3)
        w.lock_works = False
        w.lid = "closed"; w.run(60)
        self.assertEqual(len(w.kinds("LOCK")), 2)
        self.assertEqual(len(w.kinds("WARN")), 1)

    def test_E_reboot_while_closed_returns_to_server(self):
        w = World("open").run(5); w.login(); w.run(3)
        w.lid = "closed"; w.run(10)
        rebooted = World("closed").run(120)         # fresh memory, fresh /run
        self.assertEqual(rebooted.kinds("START"), [])

    def test_F_close_while_only_greeter_showing(self):
        w = World("open").run(5)
        self.assertTrue(w.has_greeter())
        w.lid = "closed"; w.run(10)
        self.assertEqual(len(w.kinds("STOP")), 1)
        self.assertEqual(w.unit, "inactive")
        self.assertIn(SSH, w.sessions)

    def test_F_race_login_then_immediate_close_never_kills_session(self):
        w = World("open").run(5)
        w.login()                                   # Enter pressed...
        w.lid = "closed"                            # ...and lid shut at once
        w.run(60)
        self.assertEqual(w.kinds("STOP"), [])
        self.assertTrue(w.has_desktop())
        self.assertEqual(len(w.kinds("LOCK")), 1)   # and it is locked

    def test_F_slow_session_start_after_auth_is_not_killed(self):
        w = World("open").run(5)
        w.login_delay = 12.0                        # slow PAM / session setup
        w.login(); w.lid = "closed"
        w.run(60)
        self.assertEqual(w.kinds("STOP"), [])
        self.assertTrue(w.has_desktop())

    def test_F_session_appearing_during_stop_aborts_it(self):
        w = World("open").run(5)
        def race():
            w.sessions = [s for s in w.sessions if s.cls != "greeter"] + [DESKTOP()]
        w.before_stop = race
        w.lid = "closed"; w.run(30)
        self.assertEqual(len(w.kinds("STOP")), 1)
        self.assertEqual(len(w.kinds("STOP_ABORTED")), 1)
        self.assertEqual(w.unit, "active")
        self.assertTrue(w.has_desktop())

    def test_F_stop_rechecks_fresh_state(self):
        w = World("open").run(5)
        w.lid = "closed"
        w.run(3.75)                                 # just before stop grace expires
        w.sessions.append(DESKTOP())                # session appears at the last moment
        w.sessions = [s for s in w.sessions if s.cls != "greeter"]
        w.run(10)
        self.assertEqual(w.kinds("STOP"), [])

    def test_rapid_lid_events_start_at_most_one_greeter(self):
        w = World("closed").run(5)
        for i in range(40):                         # 40 toggles, 0.25 s apart
            w.lid = "open" if i % 2 == 0 else "closed"
            w.run(0.25)
        w.lid = "open"; w.run(10)
        self.assertEqual(len(w.kinds("START")), 1)
        self.assertEqual(w.kinds("STOP"), [])

    def test_G_desktop_off_with_lid_open_stays_off(self):
        w = World("open").run(5); w.login(); w.run(3)
        w.suppressed = True                         # hyprlandfiles off
        w.logout()                                  # compositor exits cleanly
        w.run(120)
        self.assertEqual(len(w.kinds("START")), 1)  # never restarted
        self.assertEqual(w.unit, "inactive")
        self.assertIn(("CHVT"), [k for _, k, _ in w.log])

    def test_G_close_open_cycle_clears_manual_off(self):
        w = World("open").run(5)
        w.suppressed = True; w.run(10)
        self.assertEqual(w.unit, "inactive")
        w.lid = "closed"; w.run(5)
        w.lid = "open"; w.run(5)
        self.assertFalse(w.suppressed)
        self.assertEqual(len(w.kinds("START")), 2)

    def test_G_bounce_shorter_than_settle_does_not_clear_manual_off(self):
        w = World("open").run(5)
        w.suppressed = True; w.run(10)
        w.lid = "closed"; w.run(0.5)
        w.lid = "open"; w.run(10)
        self.assertTrue(w.suppressed)

    def test_G_desktop_on_clears_manual_off(self):
        w = World("open").run(5)
        w.suppressed = True; w.run(10)
        w.suppressed = False; w.run(5)              # hyprlandfiles on
        self.assertEqual(len(w.kinds("START")), 2)

    def test_G_desktop_on_while_closed_shows_greeter_and_does_not_autolock(self):
        w = World("closed").run(5)
        w.requested = True; w.run(5)
        self.assertTrue(w.has_greeter())
        w.login(); w.run(30)
        self.assertEqual(w.kinds("LOCK"), [])
        w.lid = "open"; w.run(3); w.lid = "closed"; w.run(10)
        self.assertFalse(w.requested)
        self.assertEqual(len(w.kinds("LOCK")), 1)

    def test_logout_with_lid_open_keeps_greeter(self):
        w = World("open").run(5); w.login(); w.run(3)
        w.logout(); w.run(30)
        self.assertEqual(w.kinds("STOP"), [])

    def test_session_ends_while_lid_closed_returns_to_headless(self):
        w = World("open").run(5); w.login(); w.run(3)
        w.lid = "closed"; w.run(5)
        w.logout(); w.run(15)                       # e.g. compositor crash
        self.assertEqual(len(w.kinds("STOP")), 1)
        self.assertEqual(w.unit, "inactive")

    def test_greeter_crash_loop_backs_off(self):
        w = World("open").run(2)
        for _ in range(10):
            w.unit = "failed"; w.sessions = [SSH]; w.run(3)
        self.assertLessEqual(len(w.kinds("START")), CFG.start_burst + 1)
        self.assertEqual(len(w.kinds("WARN")), 1)

    def test_unknown_lid_is_treated_as_closed(self):
        w = World("unknown").run(30)
        self.assertEqual(w.kinds("START"), [])

    def test_ssh_and_console_sessions_never_trigger_anything(self):
        w = World("closed")
        w.sessions.append(Session("3", "alice", "seat0", "user", "tty", "login", "active"))
        w.run(60)
        self.assertEqual(w.log, [])

    def test_docked_policy_strict_ignores_external_display(self):
        w = World("open").run(5); w.login(); w.run(3)
        w.externals = True
        w.lid = "closed"; w.run(10)
        self.assertEqual(len(w.kinds("LOCK")), 1)

    def test_docked_policy_keep_external_skips_lock(self):
        cfg = Config(docked_policy="keep-external")
        w = World("open", cfg).run(5); w.login(); w.run(3)
        w.externals = True
        w.lid = "closed"; w.run(10)
        self.assertEqual(w.kinds("LOCK"), [])



class ConsolePanel(unittest.TestCase):
    """The internal panel follows the lid only while the text console owns it."""

    def test_closed_lid_boot_powers_panel_off(self):
        w = World("closed", panel="on").run(10)
        self.assertEqual(w.panel_log(), ["off"])
        self.assertEqual(w.kinds("START"), [])

    def test_lid_open_powers_panel_on_before_greeter(self):
        w = World("closed", panel="on").run(5)
        w.lid = "open"; w.run(5)
        self.assertEqual([e[1] for e in w.log if e[1] in ("PANEL", "START")],
                         ["PANEL", "PANEL", "START"])
        self.assertEqual(w.panel_log(), ["off", "on"])
        self.assertTrue(w.has_greeter())

    def test_close_with_only_greeter_powers_panel_off_after_console_returns(self):
        w = World("open", panel="on").run(5)
        w.lid = "closed"; w.run(10)
        self.assertEqual(len(w.kinds("STOP")), 1)
        self.assertEqual(w.panel_log(), ["off"])
        self.assertEqual(w.panel, "off")
        self.assertEqual([e[1] for e in w.log if e[1] in ("CHVT", "PANEL")], ["CHVT", "PANEL"])

    def test_panel_is_left_to_the_desktop_session(self):
        w = World("open", panel="on").run(5); w.login(); w.run(3)
        w.lid = "closed"; w.panel = "off"; w.run(10)    # Hyprland's lid bind
        w.lid = "open"; w.panel = "on"; w.run(5)
        self.assertEqual(w.panel_log(), [])

    def test_session_end_while_closed_powers_panel_off(self):
        w = World("open", panel="on").run(5); w.login(); w.run(3)
        w.lid = "closed"; w.panel = "off"; w.run(10)
        w.logout(); w.run(10)                            # fbcon relights it
        self.assertEqual(w.panel_log(), ["off"])
        self.assertEqual(w.panel, "off")

    def test_desktop_on_while_closed_does_not_light_panel(self):
        w = World("closed", panel="on").run(5)
        w.requested = True; w.run(5)
        self.assertEqual(w.panel_log(), ["off"])
        self.assertTrue(w.has_greeter())

    def test_unconfirmed_panel_change_is_rate_limited(self):
        w = World("closed", panel="on"); w.panel_works = False
        w.run(65)
        self.assertEqual(w.panel_log(), ["off", "off", "off"])

    def test_panel_control_off_never_touches_panel(self):
        w = World("closed", Config(panel_control=False), panel="on").run(10)
        w.lid = "open"; w.run(5)
        self.assertEqual(w.panel_log(), [])
        self.assertEqual(len(w.kinds("START")), 1)


if __name__ == "__main__":
    unittest.main()
