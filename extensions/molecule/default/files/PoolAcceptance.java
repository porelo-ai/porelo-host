import org.fuin.porelo.machines.Credential;
import org.fuin.porelo.machines.Lease;
import org.fuin.porelo.machines.LocalPool;
import org.fuin.porelo.machines.Pool;
import org.fuin.porelo.machines.Spec;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import java.util.concurrent.TimeUnit;

/** Checks that returning a real pool lease never exposes one run's data to the next. */
public final class PoolAcceptance {
    private static final String HOME = "/home/run/left-by-pool-acceptance";
    private static final String ETC = "/etc/left-by-pool-acceptance";

    private PoolAcceptance() {}

    /** Runs on the Molecule VM; only the deliberately killed child leaves its lease open. */
    public static void main(String[] args) throws Exception {
        final Path file = Path.of(args[0]);
        final Path here = Path.of(args[1]);
        final Pool definition = Pool.read(file);
        require(definition.vms().size() == 1, "expected exactly one pool VM");
        final Pool.Vm vm = definition.vms().getFirst();
        require(
                vm.os().equals("ubuntu") && vm.accounts().equals(List.of("run")),
                "expected one Ubuntu VM with account run");
        final Credential key = Credential.of(System.getenv("PORELO_POOL_SSH"), null);
        final Path state = Path.of(System.getenv("XDG_STATE_HOME"), "porelo-machines", "pool");
        final Path dirty = state.resolve(vm.name()).resolve("run.dirty");
        final Spec spec = Spec.of("pool-acceptance", "ubuntu", "run", key);
        try (LocalPool pool =
                LocalPool.onThisHost(definition, key, state, Duration.ofSeconds(30))) {
            if (args.length == 3 && args[2].equals("hold")) {
                final Lease held = pool.acquire(spec);
                identity(held, vm);
                leaveMarkers(held);
                Files.writeString(here.resolve("held"), "markers observed\n");
                Thread.sleep(Duration.ofMinutes(2));
                throw new IOException("the renter was not killed within two minutes");
            }
            if (args.length == 3 && args[2].equals("clean")) {
                require(!Files.exists(dirty), "the CLI leg left its account dirty");
                try (Lease next = pool.acquire(spec)) {
                    identity(next, vm);
                    clean(next);
                    command(next, "test ! -e /home/acceptance && ! getent passwd acceptance");
                }
                require(!Files.exists(dirty), "the CLI leg's next return left a dirty marker");
                System.out.println("CLI leg returned: acceptance account and run data absent");
                return;
            }
            try (Lease ended = pool.acquire(spec)) {
                identity(ended, vm);
                clean(ended);
                leaveMarkers(ended);
            }
            require(!Files.exists(dirty), "normal return left a dirty marker");
            try (Lease next = pool.acquire(spec)) {
                identity(next, vm);
                clean(next);
            }
            System.out.println("normal return: home and /etc clean in the next rental");

            require(!Files.exists(here.resolve("held")), "an earlier renter left its handshake");
            final Process child =
                    new ProcessBuilder(
                                    Path.of(System.getProperty("java.home"), "bin", "java")
                                            .toString(),
                                    "-cp",
                                    System.getProperty("java.class.path"),
                                    PoolAcceptance.class.getName(),
                                    file.toString(),
                                    here.toString(),
                                    "hold")
                            .inheritIO()
                            .start();
            try {
                final long deadline = System.nanoTime() + Duration.ofSeconds(60).toNanos();
                while (!Files.exists(here.resolve("held"))) {
                    require(child.isAlive(), "renter exited before it observed both markers");
                    require(
                            System.nanoTime() < deadline,
                            "renter did not observe markers within 60 s");
                    Thread.sleep(100);
                }
                require(child.isAlive(), "renter ended before it could be killed");
                child.destroyForcibly();
                require(
                        child.waitFor(10, TimeUnit.SECONDS),
                        "killed renter did not exit within 10 s");
                require(
                        child.exitValue() == 137,
                        "expected SIGKILL exit 137, got " + child.exitValue());
                require(Files.exists(dirty), "killed renter left no dirty marker to recover");
                try (Lease next = pool.acquire(spec)) {
                    identity(next, vm);
                    clean(next);
                }
                require(
                        !Files.exists(dirty),
                        "return after killed-renter recovery left a dirty marker");
                System.out.println("killed renter: home and /etc clean in the next rental");
            } finally {
                child.destroyForcibly();
                require(child.waitFor(10, TimeUnit.SECONDS), "renter survived cleanup");
                Files.deleteIfExists(here.resolve("held"));
            }
        }
    }

    private static void identity(Lease lease, Pool.Vm vm) throws IOException {
        require(
                lease.name().equals("run@" + vm.name()) && lease.address().equals(vm.address()),
                "expected the same VM and run account, got "
                        + lease.name()
                        + " at "
                        + lease.address());
        command(
                lease,
                "test \"$(id -un)\" = run && test \"$(cat /var/lib/porelo-pool/run)\" = ready");
    }

    private static void leaveMarkers(Lease lease) throws IOException {
        command(
                lease,
                "printf 'a run\\n' > "
                        + HOME
                        + " && sudo -n sh -c \"printf 'a run\\n' > "
                        + ETC
                        + "\""
                        + " && test -s "
                        + HOME
                        + " && test -s "
                        + ETC);
    }

    private static void clean(Lease lease) throws IOException {
        command(lease, "test ! -e " + HOME + " && test ! -e " + ETC);
    }

    private static void command(Lease lease, String command) throws IOException {
        final var output = lease.ssh().run(command);
        require(
                output.status() == 0,
                "expected exit 0 for "
                        + command
                        + ", got "
                        + output.status()
                        + ": "
                        + output.all());
    }

    private static void require(boolean condition, String message) throws IOException {
        if (!condition) {
            throw new IOException(message);
        }
    }
}
