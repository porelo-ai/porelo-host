"""Prevent direct homeserver access and socket activation under the caller's identity."""

import json
from pathlib import Path

import jinja2
import yaml

ROOT = Path(__file__).resolve().parents[3]
ROLE = ROOT / "roles/matrix"


def tasks():
    return yaml.safe_load((ROLE / "tasks/main.yml").read_text())


def test_gate_socket_and_service_keep_the_peer_boundary():
    """Prevent nonmembers reaching the gate or the gate inheriting a person's identity."""
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(ROLE / "templates"), undefined=jinja2.StrictUndefined)
    socket = env.get_template("porelo-matrix-gate.socket.j2").render(matrix_account="porelo-matrix", __matrix_uid=1201)
    service = env.get_template("porelo-matrix-gate@.service.j2").render(
        matrix_account="porelo-matrix", __matrix_uid=1201
    )
    for setting in (
        "ListenStream=/run/porelo-matrix/client.sock",
        "Accept=yes",
        "SocketUser=porelo-matrix",
        "SocketGroup=porelo-people",
        "SocketMode=0660",
        "DirectoryMode=0755",
        "RemoveOnStop=yes",
    ):
        assert setting in socket.splitlines()
    for setting in (
        "User=porelo-matrix",
        "ExecStart=/usr/libexec/porelo/transports/porelo-message-transport-matrix gate",
        "StandardInput=socket",
        "NoNewPrivileges=yes",
        "PartOf=porelo-matrix-gate.socket",
    ):
        assert setting in service.splitlines()


def test_prepare_precedes_start_and_socket_units_are_installed():
    """Prevent starting the homeserver with TCP defaults or missing gate preparation."""
    entries = tasks()
    prepare_index, prepare = next(
        (i, t)
        for i, t in enumerate(entries)
        if t.get("ansible.builtin.command", {}).get("argv") == ["{{ matrix_transport_command }}", "gate", "--prepare"]
    )
    start_index = next(
        i
        for i, t in enumerate(entries)
        if t.get("ansible.builtin.systemd_service", {}).get("name") == "porelo-matrix-homeserver.service"
    )
    assert prepare_index < start_index
    assert prepare["become_user"] == "{{ matrix_account }}"
    assert prepare["ansible.builtin.command"]["creates"]
    templates = next(t for t in entries if "porelo-matrix-gate.socket" in t.get("loop", []))
    assert set(templates["loop"]) == {"porelo-matrix-gate.socket", "porelo-matrix-gate@.service"}
    assert templates["ansible.builtin.template"]["dest"] == "/etc/systemd/system/{{ item }}"
    enabled = [t["ansible.builtin.systemd_service"] for t in entries if "ansible.builtin.systemd_service" in t]
    assert any(t["name"] == "porelo-matrix-gate.socket" and t["enabled"] and t["state"] == "started" for t in enabled)


def test_homeserver_configuration_has_only_a_private_unix_listener():
    """Prevent a TCP or TLS listener from bypassing the gate."""
    entries = tasks()
    settings = next(
        t
        for t in entries
        if t.get("ansible.builtin.lineinfile", {}).get("path") == "{{ __matrix_conf }}"
        and any(isinstance(v, dict) and v.get("key") == "PORELO_MATRIX_GATE" for v in t.get("loop", []))
    )
    values = {v["key"]: v["value"] for v in settings["loop"]}
    assert values["PORELO_MATRIX_GATE"] == 1
    assert not {"port", "address", "PORELO_MATRIX_PORT", "PORELO_MATRIX_PUBLISH"} & values.keys()
    assert all(t.get("become_user") == "{{ matrix_account }}" for t in entries if "ansible.builtin.lineinfile" in t)
    assert not any("publish" in t.get("ansible.builtin.command", {}).get("argv", []) for t in entries)
    assert not any("ansible.builtin.shell" in t for t in entries)


def test_existing_tcp_units_and_person_tokens_are_removed():
    """Prevent an upgraded host retaining a TCP bypass or reusable registration credentials."""
    entries = tasks()
    retired = next(t for t in entries if "porelo-matrix-homeserver-vpn.socket" in t.get("loop", []))
    assert retired["ansible.builtin.systemd_service"]["state"] == "stopped"
    assert retired["ansible.builtin.systemd_service"]["enabled"] is False
    assert set(retired["loop"]) == {
        "porelo-matrix-homeserver-vpn.socket",
        "porelo-matrix-homeserver-vpn.service",
    }
    cleanup = next(
        t for t in entries if "host-registration-token" in str(t.get("ansible.builtin.command", {}).get("argv", []))
    )
    assert cleanup["become"] is True
    assert cleanup["become_user"] == "{{ __matrix_person }}"
    assert cleanup["ansible.builtin.command"]["argv"][:3] == ["rm", "-f", "--"]


def test_old_tcp_units_are_stopped_only_where_they_were_published():
    """Prevent a fresh host failing on the shipped, address-less unit that systemd refuses to load."""
    retired = next(t for t in tasks() if "porelo-matrix-homeserver-vpn.socket" in t.get("loop", []))
    env = jinja2.Environment()
    env.filters["split"] = str.split
    condition = env.compile_expression(retired["when"])
    for listing, acted in [
        (["porelo-matrix-homeserver-vpn.socket disabled enabled", "porelo-matrix-homeserver-vpn.service static -"], []),
        (
            ["porelo-matrix-homeserver-vpn.socket enabled enabled", "porelo-matrix-homeserver-vpn.service static -"],
            ["porelo-matrix-homeserver-vpn.socket", "porelo-matrix-homeserver-vpn.service"],
        ),
        ([], []),
    ]:
        old = {"stdout_lines": listing}
        assert [item for item in retired["loop"] if condition(item=item, __matrix_old_units=old)] == acted, listing


def test_the_transport_is_called_where_its_package_installs_it():
    """Prevent the gate, its preparation and expel calling a program the transport package does not ship."""
    shipped = "/usr/libexec/porelo/transports/porelo-message-transport-matrix"
    defaults = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
    assert defaults["matrix_transport_command"] == shipped
    for path in [ROOT / "roles/porelo/files/porelo-host-person", *ROLE.glob("templates/*.j2")]:
        assert "/usr/bin/porelo-message-transport-matrix" not in path.read_text(), path


def test_gate_gets_its_administrator_once_the_homeserver_answers():
    """Prevent a gate prepared before the homeserver ran from refusing every sign-in for want of its admin token."""
    entries = tasks()
    names = [t.get("name", "") for t in entries]
    started = names.index("Restart the Matrix homeserver now if its settings changed")
    admin = next(i for i, t in enumerate(entries) if "admin-token" in str(t.get("ansible.builtin.command", {})))
    assert admin > started
    task = entries[admin]
    assert task["ansible.builtin.command"]["argv"][1:] == ["gate", "--prepare"]
    assert task["ansible.builtin.command"]["creates"] == "{{ __matrix_dir }}/gate/admin-token"
    assert "administrator" in task["until"] and task["retries"] >= 10
    recorded = names.index("Record the completed Matrix gate preparation")
    assert recorded > admin


def test_a_gate_already_holding_its_token_passes_again():
    """Prevent every later up failing on the empty output the command gives when its creates file exists."""
    task = next(t for t in tasks() if "admin-token" in str(t.get("ansible.builtin.command", {})))
    env = jinja2.Environment(undefined=jinja2.StrictUndefined)
    env.filters["from_json"] = json.loads
    env.tests["skipped"] = lambda result: result.get("skipped", False)
    until = env.compile_expression(task["until"].strip())
    # ansible-core's command answers rc 0, no output and no change when the creates file exists.
    assert until(__matrix_administrator={"rc": 0, "stdout": "", "changed": False})
    assert until(__matrix_administrator={"rc": 0, "stdout": '{"gate":true,"administrator":true}', "changed": True})
    assert not until(__matrix_administrator={"rc": 0, "stdout": '{"gate":true,"administrator":false}', "changed": True})
    assert not until(__matrix_administrator={"rc": 1, "stdout": "", "changed": True})
