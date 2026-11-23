"""Keep every time limit of the collection its default times its group's factor, as Porelo's limits line says."""

import importlib.machinery
import importlib.util
import re
from pathlib import Path

import jinja2
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]

# Each factor different, as the lazily templated play vars hand them on: text, never a number.
FACTORS = {"services": "2.0", "machines": "3.0", "polling": "4.0", "retries": "5.0"}


def environment():
    env = jinja2.Environment(undefined=jinja2.ChainableUndefined, keep_trailing_newline=True)
    env.filters["comment"] = lambda text: ""
    env.filters["quote"] = str
    return env


def render(text, **extra):
    return environment().from_string(text).render(__porelo_host_limits=FACTORS, **extra)


def template(path):
    return render((ROOT / path).read_text())


def task(path, name):
    found = [item for item in yaml.safe_load((ROOT / path).read_text()) if item.get("name") == name]
    assert len(found) == 1, name
    return found[0]


def field(value):
    return render(str(value))


def test_the_play_vars_give_each_factor_from_the_inventory_and_one_by_default():
    limits = yaml.safe_load((ROOT / "playbooks/vars/limits.yml").read_text())["__porelo_host_limits"]
    assert {name: render(text) for name, text in limits.items()} == dict.fromkeys(FACTORS, "1.0")
    given = {"porelo_host_limits_" + name: float(value) for name, value in FACTORS.items()}
    assert {name: render(text, **given) for name, text in limits.items()} == FACTORS


def test_the_limits_line_names_all_four_in_order_with_a_digit_after_each_dot():
    line = yaml.safe_load((ROOT / "playbooks/vars/limits.yml").read_text())["__porelo_host_limits_line"]
    assert render(line) == "services=2.0,machines=3.0,polling=4.0,retries=5.0"
    assert (
        environment().from_string(line).render(__porelo_host_limits={"services": 1, "machines": 0.25, "polling": "1.5"})
        == "services=1.0,machines=0.25,polling=1.5,retries=1.0"
    )


@pytest.mark.parametrize("playbook", ["playbooks/up.yml", "playbooks/down.yml"])
def test_every_play_reads_the_factors_and_the_first_refuses_a_wrong_one_before_any_change(playbook):
    plays = yaml.safe_load((ROOT / playbook).read_text())
    assert all("vars/limits.yml" in play.get("vars_files", []) for play in plays)
    first = plays[0]["tasks"]
    include = [index for index, item in enumerate(first) if "ansible.builtin.include_tasks" in item]
    assert include and first[include[0]]["ansible.builtin.include_tasks"] == "tasks/limits.yml"
    changes = [index for index, item in enumerate(first) if "ansible.builtin.include_role" in item]
    assert not changes or include[0] < changes[0]


@pytest.mark.parametrize(
    ("value", "good"),
    [
        (1, True),
        (1.0, True),
        (0.1, True),
        (100, True),
        (0.25, True),
        (2.5, True),
        (0.09, False),
        (100.5, False),
        (0, False),
        (-1, False),
        (0.125, False),
        (True, False),
        ("1.0", False),
        (None, False),
    ],
)
def test_a_factor_is_a_number_from_0_1_to_100_with_at_most_two_digits_after_the_dot(value, good):
    check = yaml.safe_load((ROOT / "playbooks/tasks/limits.yml").read_text())[0]["ansible.builtin.assert"]
    env = environment()
    env.tests["number"] = lambda item: isinstance(item, (int, float))
    env.tests["boolean"] = lambda item: isinstance(item, bool)
    assert all(env.compile_expression(test)(__porelo_host_factor=value) for test in check["that"]) is good


def test_services_limits_follow_their_factor():
    assert (
        field(
            task(
                "roles/forge/tasks/runner.yml",
                "runner | Fetch the JDK once and check its pinned digest before unpacking",
            )["ansible.builtin.get_url"]["timeout"]
        )
        == "120"
    )
    unit = template("roles/forge/templates/porelo-host-verify@.service.j2")
    hook = template("roles/forge/templates/porelo-forge-pre-receive.j2")
    assert "--max-time 600 " in hook
    assert "TimeoutStartSec=610\n" in unit and "RuntimeMaxSec=610\n" in unit, "the judge outlasts the hook's wait"


def test_machines_limits_follow_their_factor():
    for play in yaml.safe_load((ROOT / "playbooks/up.yml").read_text()):
        assert field(play["module_defaults"]["ansible.builtin.apt"]["lock_timeout"]) == "900"
    check = task("roles/check/tasks/main.yml", "Ask the machine")["ansible.builtin.script"]["cmd"]
    assert field(re.search(r"--wait-packages ({{.*?}})", check)[1]) == "900"
    assert (
        field(
            task(
                "roles/forge/tasks/accounts.yml", "accounts | Wait for each account's user manager and its session bus"
            )["ansible.builtin.wait_for"]["timeout"]
        )
        == "180"
    )
    forgejo = task("roles/forge/tasks/service.yml", "service | Wait until Forgejo answers on its private socket")
    assert (field(forgejo["retries"]), forgejo["delay"]) == ("90", 2)
    assert "TimeoutStartSec=900s\n" in template("roles/porelo/templates/porelo-host-follow.service.j2")
    assert (
        field(
            task("roles/matrix/tasks/main.yml", "Wait for the homeserver account's user manager and its session bus")[
                "ansible.builtin.wait_for"
            ]["timeout"]
        )
        == "180"
    )
    homeserver = [
        item
        for item in yaml.safe_load((ROOT / "roles/matrix/tasks/main.yml").read_text())
        if item.get("register") == "__matrix_administrator" and "until" in item
    ]
    assert len(homeserver) == 1 and (field(homeserver[0]["retries"]), homeserver[0]["delay"]) == ("60", 3)
    down = (ROOT / "roles/matrix/tasks/down.yml").read_text()
    assert (
        "for _ in $(seq 1 {{ (10 * __porelo_host_limits.machines | float) | round(6) | round(0, 'ceil') | int }}); do"
        in down
    )
    pool = yaml.safe_load((ROOT / "roles/vm_pool/tasks/vm.yml").read_text())
    address = [item for item in pool if item.get("register") == "__vm_pool_address"][0]
    assert field(address["ansible.builtin.command"]["argv"][-1]) == "900"
    ready = [item for item in pool if item.get("register") == "__vm_pool_ready"][0]
    assert "ConnectTimeout=15" in [field(arg) for arg in ready["ansible.builtin.command"]["argv"]]
    assert (field(ready["retries"]), ready["delay"]) == ("540", 5)
    clock = [item for item in pool if item.get("register") == "__vm_pool_agent"][0]
    assert field(clock["ansible.builtin.command"]["argv"][1]) == "30"
    assert (field(clock["retries"]), clock["delay"]) == ("120", 3)


def test_polling_limits_follow_their_factor():
    proxy = template("roles/forge/templates/forgejo-runner-proxy.container.j2")
    assert "do sleep 20; done" in proxy
    timer = template("roles/porelo/templates/porelo-host-follow.timer.j2")
    assert "OnUnitActiveSec=1200s\n" in timer and "OnCalendar" not in timer


def test_retries_limits_follow_their_factor():
    fetch = task(
        "roles/forge/tasks/runner.yml", "runner | Fetch the JDK once and check its pinned digest before unpacking"
    )
    assert (field(fetch["retries"]), field(fetch["delay"])) == ("35", "600")
    for path in [
        "roles/forge/templates/forgejo.container.j2",
        "roles/forge/templates/forgejo-runner.container.j2",
        "roles/forge/templates/forgejo-runner-proxy.container.j2",
    ]:
        assert "RestartSec=50\n" in template(path), path
    assert "RestartSec=25\n" in template("roles/vm_pool/templates/porelo-pool-revert.service.j2")


def test_a_retry_count_is_rounded_up_and_never_below_one():
    fetch = task(
        "roles/forge/tasks/runner.yml", "runner | Fetch the JDK once and check its pinned digest before unpacking"
    )
    least = environment().from_string(str(fetch["retries"])).render(__porelo_host_limits={"retries": "0.1"})
    assert least == "1"


def test_the_matrix_gate_gets_the_limits_line_before_its_verb():
    unit = (
        environment()
        .from_string((ROOT / "roles/matrix/templates/porelo-matrix-gate@.service.j2").read_text())
        .render(__porelo_host_limits_line="services=2.0,machines=3.0,polling=4.0,retries=5.0")
    )
    assert re.search(
        r"^ExecStart=/usr/libexec/porelo/transports/porelo-message-transport-matrix "
        r"--limits services=2\.0,machines=3\.0,polling=4\.0,retries=5\.0 gate$",
        unit,
        re.M,
    )


def load_check():
    loader = importlib.machinery.SourceFileLoader(
        "porelo_host_check_factors", str(ROOT / "roles/check/files/porelo-host-check")
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_the_check_program_reads_the_limits_line_as_porelo_writes_it():
    check = load_check()
    assert check.factors("") == {"services": 1.0, "machines": 1.0, "polling": 1.0, "retries": 1.0}
    assert check.factors("polling=4,services=2.5") == {"services": 2.5, "machines": 1.0, "polling": 4.0, "retries": 1.0}
    for wrong in [
        "services=0.09",
        "services=100.5",
        "services=01",
        "services=1,services=2",
        "speed=1",
        "services",
        "services=1.234",
        "services= 1",
        "services=+1",
        "services=1e1",
        "services=1,",
    ]:
        with pytest.raises(ValueError):
            check.factors(wrong)


def test_the_check_program_waits_and_looks_by_its_factors():
    check = load_check()
    machine = check.Machine("", True, check.factors("services=2,polling=4"))
    assert (machine.reach_seconds(), machine.probe_seconds(), machine.package_poll_seconds()) == (20.0, 10.0, 8.0)
    plain = check.Machine("", True)
    assert (plain.reach_seconds(), plain.probe_seconds(), plain.package_poll_seconds()) == (10.0, 5.0, 2.0)


def test_the_host_program_reads_the_limits_line_from_its_own_configuration_and_down_takes_it_away():
    install = task(
        "roles/porelo/tasks/install.yml", "install | Write the host's time factors and day bounds for the host program"
    )
    copy = install["ansible.builtin.copy"]
    assert copy["dest"] == "/etc/porelo-host/host.yml" and copy["owner"] == "root" and copy["mode"] == "0644"
    env = environment()
    env.filters["to_nice_yaml"] = lambda value, indent=2: yaml.safe_dump(value, indent=indent, default_flow_style=False)
    written = env.from_string(copy["content"]).render(
        __porelo_host_limits_line="services=2.0,machines=1.0,polling=1.0,retries=1.0",
        __porelo_host_days={"certificate_days": "30", "lent_token_days": "2"},
    )
    assert yaml.safe_load(written) == {
        "limits": "services=2.0,machines=1.0,polling=1.0,retries=1.0",
        "certificate_days": 30,
        "lent_token_days": 2,
    }
    removed = task("roles/porelo/tasks/down.yml", "down | Remove the host's time factors")["ansible.builtin.file"]
    assert removed == {"path": "/etc/porelo-host/host.yml", "state": "absent"}


def test_a_factor_with_a_fraction_rounds_the_true_product_not_the_float_error():
    """180 * 1.1 is 198.00000000000003 in doubles: rounded up naively the pool waits one try more than the rule says."""
    pool = yaml.safe_load((ROOT / "roles/vm_pool/tasks/vm.yml").read_text())
    ready = [item for item in pool if item.get("register") == "__vm_pool_ready"][0]
    tries = environment().from_string(ready["retries"]).render(__porelo_host_limits={"machines": "1.1"})
    assert tries == "198"


def test_a_factor_with_a_digit_too_many_far_down_is_refused():
    check = yaml.safe_load((ROOT / "playbooks/tasks/limits.yml").read_text())[0]["ansible.builtin.assert"]
    env = environment()
    env.tests["number"] = lambda item: isinstance(item, (int, float))
    env.tests["boolean"] = lambda item: isinstance(item, bool)
    for value, good in [(1.000000001, False), (0.29, True), (99.99, True), (1.1, True)]:
        assert all(env.compile_expression(test)(__porelo_host_factor=value) for test in check["that"]) is good, value


def test_the_wait_for_forgejo_asks_each_time_by_the_machines_factor():
    forgejo = task("roles/forge/tasks/service.yml", "service | Wait until Forgejo answers on its private socket")
    argv = forgejo["ansible.builtin.command"]["argv"]
    assert field(argv[argv.index("--max-time") + 1]) == "15"


def test_the_play_vars_give_each_day_bound_from_the_inventory_and_porelos_default():
    days = yaml.safe_load((ROOT / "playbooks/vars/limits.yml").read_text())["__porelo_host_days"]
    env = environment()
    assert env.from_string(days["certificate_days"]).render() == "7"
    assert env.from_string(days["lent_token_days"]).render() == "1"
    assert env.from_string(days["certificate_days"]).render(porelo_host_certificate_days=30) == "30"
    assert env.from_string(days["lent_token_days"]).render(porelo_host_lent_token_days=2) == "2"


@pytest.mark.parametrize(
    ("value", "good"),
    [(1, True), (7, True), (3650, True), (0, False), (3651, False), (-1, False), (1.5, False), (7.0, False)]
    + [(True, False), ("7", False), (None, False)],
)
def test_a_day_bound_is_a_whole_number_from_1_to_3650(value, good):
    checks = yaml.safe_load((ROOT / "playbooks/tasks/limits.yml").read_text())
    check = [item for item in checks if "day bound" in item["name"]][0]["ansible.builtin.assert"]
    env = environment()
    env.tests["integer"] = lambda item: isinstance(item, int)
    env.tests["boolean"] = lambda item: isinstance(item, bool)
    assert all(env.compile_expression(test)(__porelo_host_day_bound=value) for test in check["that"]) is good


def test_a_role_called_on_its_own_gets_the_plays_limits_file():
    """The check reads the limits the plays' vars file gives; a call outside a play hands it the same file."""
    side_effect = yaml.safe_load((ROOT / "extensions/molecule/default/side_effect.yml").read_text())[0]["tasks"]
    alone = [item for item in side_effect if "include_role -a name=porelo.host.check" in str(item)]
    assert alone
    for item in alone:
        assert (
            "-e @/root/.ansible/collections/ansible_collections/porelo/host/playbooks/vars/limits.yml"
            in item["ansible.builtin.shell"]["cmd"]
        )
