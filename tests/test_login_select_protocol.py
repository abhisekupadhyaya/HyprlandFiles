"""Exercise audited package transport and the unmodified wrong-password branch.

All credentials are synthetic sentinels. No real daemon, password or login.
"""
import ast
import contextlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT/'tests/fixtures'
from types import SimpleNamespace
tools = SimpleNamespace()
exec(compile((ROOT/'patches/nwg-greetd-ipc.py').read_text(), 'patched-ipc', 'exec'),
     namespace := {'eprint': lambda *a, **k: print(*a, file=__import__('sys').stderr)})
tools.greetd = namespace['greetd']


def frame(value):
    data = json.dumps(value, ensure_ascii=False).encode('utf-8')
    return len(data).to_bytes(4, 'little') + data


class FragmentedClient:
    def __init__(self, data, maximum=1):
        self.data = bytearray(data)
        self.maximum = maximum
        self.sent = b''

    def sendall(self, data):
        self.sent += data

    def recv(self, count):
        n = min(count, self.maximum, len(self.data))
        data = bytes(self.data[:n])
        del self.data[:n]
        return data


class Protocol(unittest.TestCase):
    def invoke(self, client, request):
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            result = tools.greetd(client, request)
        return result, output.getvalue()

    def test_fragmented_header_and_large_unicode_body(self):
        message = '確認 ' * 100
        client = FragmentedClient(frame({'type':'auth_message', 'auth_message':message}))
        result, _ = self.invoke(client, {'type':'create_session', 'username':'test-user'})
        self.assertTrue(result['auth_message'] == message, 'Unicode IPC payload was corrupted')
        self.assertEqual(int.from_bytes(client.sent[:4], 'little'), len(client.sent)-4)

    def test_two_responses_preserve_packet_boundaries(self):
        client = FragmentedClient(frame({'type':'success'})+frame({'type':'auth_message'}), maximum=4096)
        first, _ = self.invoke(client, {'type':'cancel_session'})
        second, _ = self.invoke(client, {'type':'create_session'})
        self.assertEqual(first['type'], 'success')
        self.assertEqual(second['type'], 'auth_message')

    def test_neither_request_nor_response_payload_is_logged(self):
        sentinel = 'synthetic-credential-sentinel'
        client = FragmentedClient(frame({'type':'error','description':sentinel,'error_type':'auth_error'}))
        result, output = self.invoke(client, {'type':'post_auth_message_response','response':sentinel})
        self.assertTrue(sentinel not in output, 'Credential payload appeared in diagnostics')
        self.assertEqual(result['error_type'], 'auth_error')
        self.assertIn('request type = post_auth_message_response', output)

    def test_eof_during_header_fails_closed(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(ConnectionError):
                tools.greetd(FragmentedClient(b'\x20\x00'), {'type':'create_session'})

    def test_eof_during_body_fails_closed(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(ConnectionError):
                tools.greetd(FragmentedClient((20).to_bytes(4,'little')+b'{}'), {'type':'create_session'})

    def test_oversized_frame_rejected_before_body(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(ValueError):
                tools.greetd(FragmentedClient((1024*1024+1).to_bytes(4,'little')), {'type':'create_session'})

    def test_non_object_response_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(ValueError):
                tools.greetd(FragmentedClient(frame([])), {'type':'create_session'})

    def test_native_wrong_password_branch_never_requests_session_start(self):
        # Extract the actual packaged method as-is, avoiding GTK/display setup.
        tree = ast.parse((MODULES/'nwg_login.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'GreeterWindow')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'login')
        client = Mock(side_effect=[{'type':'success'},
                                   {'type':'auth_message','auth_message_type':'secret'},
                                   {'type':'error','error_type':'auth_error'}])
        save = Mock()
        namespace = {'greetd':client, 'save_json':save, 'eprint':Mock()}
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'packaged-login-method', 'exec'), namespace)
        window = SimpleNamespace(client=object(), combo_user=Mock(), combo_session=Mock(),
                                 entry_password=Mock(), lbl_message=Mock(), cache={},
                                 settings={'env-vars':[]}, voc={'login-failed':'Rejected'}, log=False)
        window.combo_user.get_active_id.return_value = 'test-user'
        window.combo_session.get_active_id.return_value = '/usr/local/bin/hf-session'
        window.entry_password.get_text.return_value = 'synthetic-input'
        namespace['login'](window, None)
        self.assertEqual(client.call_count, 3)
        self.assertTrue(all(call.args[1]['type'] != 'start_session' for call in client.call_args_list))
        window.entry_password.set_text.assert_called_once_with('')
        window.lbl_message.set_text.assert_called_once_with('Rejected')
        save.assert_not_called()


if __name__ == '__main__':
    unittest.main()
