
#!/usr/bin/env python3
"""Create the three-host lab and test explicit forwarding rules."""

import os
import subprocess
import time
from datetime import datetime
from functools import partial

from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.topo import SingleSwitchTopo
from mininet.log import setLogLevel


def ovs(*arguments):
    # Display each command and stop if it fails.
    command = ["ovs-ofctl", *arguments]
    print("\n$", " ".join(command), flush=True)
    subprocess.run(command, check=True)


def main():
    # Root privileges are needed to create the emulated network.
    if os.geteuid() != 0:
        raise SystemExit(
            "Run with: sudo env MN_SWITCH=ovsk "
            "python3 -u exp2_flows.py"
        )

    # Select the kernel or userspace datapath.
    selection = os.environ.get("MN_SWITCH", "ovsk")

    if selection == "ovsk":
        datapath = "kernel"
    elif selection == "ovs,datapath=user":
        datapath = "user"
    else:
        raise SystemExit(
            f"Unsupported MN_SWITCH value: {selection}"
        )

    print(
        "Run time:",
        datetime.now().astimezone().isoformat(),
        flush=True,
    )
    print("Selected datapath:", datapath, flush=True)

    # Set the datapath and secure mode when creating the switch.
    switch_class = partial(
        OVSSwitch,
        datapath=datapath,
        failMode="secure",
    )

    # Assumption: h1, h2 and h3 connect to ports 1, 2 and 3.
    # No controller is used. The script installs the rules itself.
    net = Mininet(
        topo=SingleSwitchTopo(k=3),
        controller=None,
        switch=switch_class,
        autoSetMacs=True,
        build=False,
    )

    try:
        net.build()
        net.start()

        # Display port mappings and remove any existing flow entries.
        ovs("show", "s1")
        ovs("del-flows", "s1")

        # ARP enables address discovery.
        ovs(
            "add-flow",
            "s1",
            "priority=100,arp,actions=flood",
        )

        # Each IP rule forwards traffic to its destination host.
        for port in range(1, 4):
            ovs(
                "add-flow",
                "s1",
                f"priority=100,ip,nw_dst=10.0.0.{port},"
                f"actions=output:{port}",
            )

        print(
            "\n=== Flow counters before ping ===",
            flush=True,
        )
        ovs("dump-flows", "s1")

        print("\n=== Connectivity test ===", flush=True)
        loss = net.pingAll()
        print(
            f"Measured packet loss: {loss}%",
            flush=True,
        )

        print(
            "\n=== Flow counters immediately after ping ===",
            flush=True,
        )
        ovs("dump-flows", "s1")

        # Take another snapshot without running another ping test.
        # This checks whether the displayed counters change with time.
        time.sleep(2)

        print(
            "\n=== Flow counters two seconds later ===",
            flush=True,
        )
        ovs("dump-flows", "s1")

        # Testing: compare ping results and both counter snapshots.
        # Limits: this script tests basic connectivity only.
        # It does not repeat the manual priority and table-miss tests.
        if loss != 0:
            raise RuntimeError(
                "Connectivity test failed; inspect the saved output."
            )

    finally:
        # Stop the lab even if a command or test fails.
        # If cleanup is incomplete, use sudo mn -c before retrying.
        net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    main()
