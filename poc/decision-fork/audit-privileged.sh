#!/usr/bin/env bash
# Part 2 and part 3 of the live network test. This file runs ON legion-t5, as root,
# because ptrace_scope is 1 there and tcpdump needs root. security-test.sh copies it
# and starts it. It expects the container decision-fork-audit on the host network,
# with the server on port 11437.
#
# Usage (as root on legion-t5): bash audit-privileged.sh /home/peppe/decision-fork/audit
set -uo pipefail

OUT=${1:-/home/peppe/decision-fork/audit}
PORT=11437
REQ='{"instructions":"Answer the question.","schema":{"d":{"type":"boolean","description":"Is the statement true?"}},"contexts":["Is Paris in France?"]}'

pid=$(cat "$OUT/pid.txt")
echo "[2/3] strace on process $pid"
timeout 90 strace -f -p "$pid" -e trace=network,openat -o "$OUT/strace.log" >/dev/null 2>&1 &
strace_pid=$!
sleep 3
curl -s -m 300 "http://127.0.0.1:$PORT/v1/decision" -H 'Content-Type: application/json' \
  -d "$REQ" > "$OUT/host-network.json" || true
sleep 5
kill "$strace_pid" 2>/dev/null || true
wait "$strace_pid" 2>/dev/null || true

echo "    answer: $(head -c 120 "$OUT/host-network.json")"
echo "    connect() lines in total: $(grep -c 'connect(' "$OUT/strace.log" 2>/dev/null || echo 0)"
echo "    connect() to a non-local address:"
grep 'connect(' "$OUT/strace.log" 2>/dev/null | grep 'AF_INET' | grep -v '127.0.0.1\|::1' | head -5 || echo "    none"
echo "    opens of resolv.conf or hosts: $(grep -c 'resolv.conf\|/etc/hosts' "$OUT/strace.log" 2>/dev/null || echo 0)"

echo "[3/3] packet capture"
tcpdump -i any -n -w "$OUT/capture.pcap" 'not host 127.0.0.1' >/dev/null 2>&1 &
tcpdump_pid=$!
sleep 2
curl -s -m 300 "http://127.0.0.1:$PORT/v1/decision" -H 'Content-Type: application/json' \
  -d "$REQ" > /dev/null || true
sleep 3
kill "$tcpdump_pid" 2>/dev/null || true
sleep 1
echo "    DNS packets: $(tcpdump -r "$OUT/capture.pcap" -n port 53 2>/dev/null | wc -l)"
echo "    outgoing TCP handshakes: $(tcpdump -r "$OUT/capture.pcap" -n 'tcp[tcpflags] == tcp-syn' 2>/dev/null | wc -l)"
