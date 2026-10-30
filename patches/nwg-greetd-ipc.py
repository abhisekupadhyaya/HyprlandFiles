# HyprlandFiles maintenance patch for nwg-hello 0.4.2. Replaces only its IPC transport.
# Credential redaction follows the current upstream fix; request/response types
# are sufficient for diagnostics, so no authentication payload is logged.
import json


def _read_exact(client, count):
    chunks = []
    while count:
        chunk = client.recv(count)
        if not chunk:
            raise ConnectionError("greetd closed its IPC connection")
        chunks.append(chunk)
        count -= len(chunk)
    return b"".join(chunks)


def greetd(client, json_req, log=False):
    eprint("greetd: request type = {}".format(json_req.get("type", "unknown")), log=log)
    request = json.dumps(json_req).encode("utf-8")
    client.sendall(len(request).to_bytes(4, "little") + request)
    length = int.from_bytes(_read_exact(client, 4), "little")
    if not 0 < length <= 1024 * 1024:
        raise ValueError("greetd IPC response length is outside the allowed bound")
    response = json.loads(_read_exact(client, length).decode("utf-8"))
    if not isinstance(response, dict):
        raise ValueError("greetd IPC response is not an object")
    eprint("greetd: response type = {}".format(response.get("type", "unknown")), log=log)
    return response
