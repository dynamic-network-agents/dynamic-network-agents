#!/usr/bin/env bash
# Docker Desktop's kernel has built-in OVS support. The image's older init
# scripts incorrectly insist on a separate openvswitch kernel module.
set -euo pipefail

mkdir -p /var/run/openvswitch /var/log/openvswitch /etc/openvswitch

if ! ovs-appctl -t ovsdb-server version >/dev/null 2>&1; then
    if [[ ! -f /etc/openvswitch/conf.db ]]; then
        ovsdb-tool create /etc/openvswitch/conf.db \
            /usr/share/openvswitch/vswitch.ovsschema
    fi
    ovsdb-server /etc/openvswitch/conf.db \
        --remote=punix:/var/run/openvswitch/db.sock \
        --pidfile=/var/run/openvswitch/ovsdb-server.pid \
        --detach --log-file=/var/log/openvswitch/ovsdb-server.log
fi

ovs-vsctl --timeout=15 --no-wait init

if ! ovs-appctl -t ovs-vswitchd version >/dev/null 2>&1; then
    ovs-vswitchd unix:/var/run/openvswitch/db.sock \
        --pidfile=/var/run/openvswitch/ovs-vswitchd.pid \
        --detach --log-file=/var/log/openvswitch/ovs-vswitchd.log
fi

ovs-appctl -t ovsdb-server version
ovs-appctl -t ovs-vswitchd version
echo '[mac-trial] OVS userspace daemons ready; no kernel module loading attempted.'

# The vendor entry point invokes this exact service-start command again.
# Verify the daemons here instead of invoking the old module-loading script.
# Other service operations retain their normal behavior.
service() {
    if [[ $# -eq 2 && $1 == openvswitch-switch && $2 == start ]]; then
        ovs-appctl -t ovsdb-server version >/dev/null &&
            ovs-appctl -t ovs-vswitchd version >/dev/null
    else
        command /usr/sbin/service "$@"
    fi
}
export -f service

if [[ ${1:-} == --check ]]; then
    # Check that the vendor's child Bash also inherits the compatibility hook.
    /bin/bash -c 'service openvswitch-switch start'
    cleanup() {
        ip link del trial-v0 >/dev/null 2>&1 || true
        ovs-vsctl --timeout=5 --if-exists del-br trial-br >/dev/null 2>&1 || true
    }
    trap cleanup EXIT
    ovs-vsctl --timeout=15 add-br trial-br
    ip link show trial-br
    ovs-dpctl show
    ip link add trial-v0 type veth peer name trial-v1
    ip link set trial-v0 up
    tc qdisc add dev trial-v0 root netem delay 10ms
    tc qdisc show dev trial-v0
    tc qdisc del dev trial-v0 root
    ip link del trial-v0
    ovs-vsctl --timeout=15 del-br trial-br
    trap - EXIT
    echo NETWORK_PROBE_OK
    exit 0
fi

exec /bin/bash /opt/simulator/start.sh
