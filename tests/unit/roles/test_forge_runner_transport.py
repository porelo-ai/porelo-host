"""Prevent runner traffic bypassing the token gate or exposing forge and cache ports."""

import json
import re
from pathlib import Path

import yaml
from jinja2 import Environment, StrictUndefined

ROOT = Path(__file__).resolve().parents[3]
ROLE = ROOT / "roles/forge"


def tasks(name):
    return yaml.safe_load((ROLE / f"tasks/{name}.yml").read_text())


def template(name):
    return (ROLE / f"templates/{name}.j2").read_text()


def test_runner_socket_uses_token_gate_and_runner_primary_group():
    """Prevent jobs inheriting browser identity or other host accounts opening their gate."""
    socket = template("porelo-forge-runner.socket")
    for line in (
        "ListenStream=/run/porelo-forge/runner.sock",
        "Accept=yes",
        "SocketUser={{ forge_account }}",
        "SocketGroup={{ __forge_users.results[1].group }}",
        "SocketMode=0660",
        "DirectoryMode=0755",
    ):
        assert line in socket.splitlines()
    service = template("porelo-forge-runner@.service")
    assert "ExecStart=/usr/local/libexec/porelo-forge-gate --runner --upstream {{ __forge_socket }}" in service
    assert "--web" not in service
    installed = next(t["loop"] for t in tasks("service") if t.get("ansible.builtin.template") and "loop" in t)
    assert {"porelo-forge-runner.socket", "porelo-forge-runner@.service"} <= set(installed)
    started = next(t["loop"] for t in tasks("service") if t.get("ansible.builtin.systemd_service") and "loop" in t)
    assert "porelo-forge-runner.socket" in started
    handlers = yaml.safe_load((ROLE / "handlers/main.yml").read_text())
    assert "porelo-forge-runner.socket" in handlers[-1]["loop"]
    down = tasks("down")
    units = next(t["loop"] for t in down if "__forge_down_gate_units" == t.get("register"))
    assert "porelo-forge-runner.socket" in units
    assert "porelo-forge-runner@*.service" in next(
        t["ansible.builtin.command"]["argv"] for t in down if "ansible.builtin.command" in t
    )


def test_proxy_has_only_loopback_listeners_and_the_runner_socket():
    """Prevent a public forge listener or an upstream socket bypass in the proxy."""
    proxy = template("forgejo-runner-proxy.container")
    variables = yaml.safe_load((ROLE / "vars/main.yml").read_text())
    assert re.fullmatch(
        r"docker.io/alpine/socat:[0-9]+(?:\.[0-9]+){3}@sha256:[0-9a-f]{64}", variables["__forge_runner_proxy_image"]
    )
    assert "Image={{ __forge_runner_proxy_image }}" in proxy
    assert "ContainerName=forgejo-runner-proxy" in proxy
    assert [line for line in proxy.splitlines() if line.startswith("Volume=")] == [
        "Volume=/run/porelo-forge/runner.sock:/run/porelo-forge/runner.sock"
    ]
    assert "GroupAdd=keep-groups" in proxy
    assert "PublishPort=" not in proxy and "Network=host" not in proxy
    assert proxy.count("TCP-LISTEN:") == 2
    for port in ("forge_http_port", "forge_git_port"):
        assert f"TCP-LISTEN:{{{{ {port} }}}},bind=127.0.0.1,reuseaddr,fork" in proxy
    assert proxy.count("UNIX-CONNECT:/run/porelo-forge/runner.sock") == 2
    # busybox's wait has no -n: it would wait for both listeners and leave the namespace owner half up.
    assert "wait -n" not in proxy
    assert "while kill -0 $$web 2>/dev/null && kill -0 $$git 2>/dev/null; do sleep 5; done; exit 1" in proxy
    runner_tasks = tasks("runner")
    probe = next(t for t in runner_tasks if t.get("register") == "__forge_runner_proxy_image_there")
    assert probe["ansible.builtin.command"]["argv"] == ["podman", "image", "exists", "{{ __forge_runner_proxy_image }}"]
    pull = next(
        t
        for t in runner_tasks
        if t.get("ansible.builtin.command", {}).get("argv")
        == ["podman", "pull", "--quiet", "{{ __forge_runner_proxy_image }}"]
    )
    assert pull["when"] == "__forge_runner_proxy_image_there.rc == 1"
    assert pull["become_user"] == "{{ forge_runner_account }}"


def test_runner_and_registration_join_the_proxy_before_using_loopback():
    """Prevent broken registration or host cache exposure outside the shared namespace."""
    runner = template("forgejo-runner.container")
    for line in (
        "Network=container:forgejo-runner-proxy",
        "After=forgejo-runner-proxy.service",
        "Requires=forgejo-runner-proxy.service",
    ):
        assert line in runner.splitlines()
    assert "PublishPort=" not in runner
    runner_tasks = tasks("runner")
    index, register = next(
        (i, t)
        for i, t in enumerate(runner_tasks)
        if t.get("no_log") and "generate-runner-token" in t.get("ansible.builtin.shell", {}).get("cmd", "")
    )
    command = register["ansible.builtin.shell"]["cmd"]
    assert "http://127.0.0.1:{{ forge_http_port }}" in command
    assert "--network container:forgejo-runner-proxy" in command
    assert "forge_address" not in command and "SSL_CERT_FILE" not in command
    assert any(
        t.get("ansible.builtin.systemd_service", {}).get("name") == "forgejo-runner-proxy.service"
        for t in runner_tasks[:index]
    )


def test_jobs_share_loopback_for_checkout_registry_and_cache():
    """Prevent jobs resolving the forge or cache to unreachable host/VPN addresses."""
    env = Environment(undefined=StrictUndefined)
    env.filters.update(comment=lambda s: "# " + s, to_json=json.dumps)
    values = dict(
        ansible_managed="managed",
        forge_runner_capacity=2,
        forge_runner_labels=[],
        forge_runner_cache_port=4000,
        forge_runner_cache_proxy_port=4001,
        forge_name="example.localhost",
        forge_job_cpus=1,
        forge_job_memory="768m",
        forge_job_pids_limit=2048,
        forge_job_omp_num_threads=1,
        __forge_runner_jdk_dir="/opt/jdk",
        __forge_runner_jdk_job_dir="/opt/job-jdk",
    )
    config = yaml.safe_load(env.from_string(template("runner-config.yml")).render(**values))
    assert config["container"]["network"] == "container:forgejo-runner-proxy"
    assert "--add-host=example.localhost:127.0.0.1" in config["container"]["options"].split()
    assert config["cache"]["host"] == "127.0.0.1"
    assert (config["cache"]["port"], config["cache"]["proxy_port"]) == (4000, 4001)
    assert "tls/" not in config["container"]["options"]
    assert config["container"]["valid_volumes"] == ["/opt/jdk"]
    defaults = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
    assert defaults["forge_variables"]["MAVEN_SNAPSHOTS_URL"] == (
        "http://{{ forge_name }}:{{ forge_http_port }}/api/packages/{{ forge_owner }}/maven"
    )


def test_existing_registration_moves_to_loopback_without_reissuing_its_token():
    """Prevent an upgraded runner keeping its previous unreachable forge address."""
    update = next((t for t in tasks("runner") if "ansible.builtin.replace" in t), None)
    assert update is not None
    assert update.get("no_log") is True
    rule = update["ansible.builtin.replace"]
    assert rule["path"] == "{{ __forge_runner_home }}/runner/.runner"
    rendered = rule["replace"].replace("{{ forge_http_port }}", "3000")
    old = json.dumps({"address": "https://old.invalid:3000", "token": "test-placeholder"})
    updated = json.loads(re.sub(rule["regexp"], rendered, old))
    assert updated == {"address": "http://127.0.0.1:3000", "token": "test-placeholder"}


def test_socket_replacement_refreshes_the_proxy_bind_mount():
    """Prevent a stale socket inode disconnecting runners after gate units change."""
    installed = next(t for t in tasks("service") if t.get("ansible.builtin.template") and "loop" in t)
    assert installed.get("register") == "__forge_gate_units"
    proxy = next(
        t
        for t in tasks("runner")
        if t.get("ansible.builtin.systemd_service", {}).get("name") == "forgejo-runner-proxy.service"
    )
    assert proxy["ansible.builtin.systemd_service"]["state"] == (
        "{{ 'restarted' if __forge_gate_units.changed else 'started' }}"
    )
    assert "PartOf=forgejo-runner-proxy.service" in template("forgejo-runner.container")


def test_every_runuser_reaches_the_accounts_own_user_manager():
    """Prevent podman under runuser failing to place its process in the account's cgroup, as crun refuses it."""
    lines = [
        line
        for path in sorted(ROOT.glob("roles/*/tasks/*.yml"))
        for line in re.sub(r"\\\n\s*", " ", path.read_text()).splitlines()
        if "runuser -u" in line and "XDG_RUNTIME_DIR=" in line
    ]
    assert lines
    for line in lines:
        runtime = re.search(r"XDG_RUNTIME_DIR=(/run/user/(?:\{\{ [^}]+ \}\}|\S+))", line).group(1)
        assert f"DBUS_SESSION_BUS_ADDRESS=unix:path={runtime}/bus" in line, line
