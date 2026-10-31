# Copyright (c) 2024 Piotr Miller. MIT; see LICENSES/nwg-hello.txt.
# Extracted from the reviewed patched Ubuntu 0.4.2-1 GreeterWindow method.
class GreeterWindow:
    def login(self, btn):
        # https://github.com/nwg-piotr/nwg-hello/issues/34
        # if not self.entry_password.get_text():
        #     eprint("Login: passwd empty, cancelling", log=self.log)
        #     self.lbl_message.set_text(self.voc["password-empty"])
        #     return
        if self.client:
            try:
                jreq = {"type": "cancel_session"}
                resp = greetd(self.client, jreq, log=self.log)
            except:
                pass

            user = self.combo_user.get_active_id()
            password = self.entry_password.get_text()
            cmd = self.combo_session.get_active_id()

            jreq = {"type": "create_session", "username": user}
            try:
                resp = greetd(self.client, jreq, log=self.log)
            except Exception as e:
                eprint(e, log=self.log)

            jreq = {"type": "post_auth_message_response", "response": password}
            resp = greetd(self.client, jreq, log=self.log)
            if "error_type" in resp and resp["error_type"] == "auth_error":
                self.lbl_message.set_text(self.voc["login-failed"])
                self.entry_password.set_text("")
            else:
                # ensure the sessions dict exists in cache
                if "sessions" not in self.cache:
                    self.cache["sessions"] = {}

                # store last used session name and username if both available
                if self.combo_user.get_active_id():
                    self.cache["user"] = self.combo_user.get_active_id()
                if self.combo_session.get_active_id():
                    self.cache["sessions"][self.cache["user"]] = self.combo_session.get_active_id()
                if self.cache["user"] and self.cache["sessions"][self.cache["user"]]:
                    eprint(f"Saving cache: {self.cache}", log=self.log)
                    # this file belongs to the 'greeter' user
                    try:
                        save_json(self.cache, "/var/cache/nwg-hello/cache.json", log=self.log)
                        eprint("Cache saved", log=self.log)
                    except Exception as e:
                        eprint(f"Error saving cache: {e}", log=self.log)

                if cmd in self.x_sessions:
                    jreq = {"type": "start_session", "cmd": ["startx", "/usr/bin/env"] + cmd.split(),
                            "env": self.settings["env-vars"]}
                else:
                    jreq = {"type": "start_session", "cmd": cmd.split(), "env": self.settings["env-vars"]}

                resp = greetd(self.client, jreq, log=self.log)
                if "type" in resp and resp["type"] == "success":
                    sys.exit()
