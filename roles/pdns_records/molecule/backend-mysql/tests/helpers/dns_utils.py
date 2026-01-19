# tests/helpers/remote_dns.py
from __future__ import annotations

import shlex
from typing import Any, Dict, List, Tuple

REMOTE_DNS_SCRIPT = r"""
import sys
import ipaddress
import dns.exception
import dns.message
import dns.query
import dns.rcode
import dns.rdatatype
import dns.reversename

def is_ip(s: str) -> bool:
    try:
        ipaddress.ip_address(s)
        return True
    except ValueError:
        return False

def normalize_qname(name: str) -> str:
    name = name.strip()
    return name if name.endswith(".") else name + "."

def ptr_qname(name_or_ip: str) -> str:
    s = name_or_ip.strip().rstrip(".")
    if s.endswith("in-addr.arpa") or s.endswith("ip6.arpa"):
        return normalize_qname(s)
    if is_ip(s):
        return dns.reversename.from_address(s).to_text()
    return normalize_qname(s)

def answers_to_short(values):
    if not values:
        return None
    uniq = sorted(set(values))
    return ",".join(uniq) if len(uniq) > 1 else uniq[0]

def main():
    # argv: name type server port timeout tcp(0/1)
    name = sys.argv[1]
    qtype = sys.argv[2].upper()
    server = sys.argv[3]
    port = int(sys.argv[4])
    timeout = float(sys.argv[5])
    use_tcp = bool(int(sys.argv[6]))

    if qtype == "PTR":
        qname = ptr_qname(name)
        rdtype = dns.rdatatype.PTR
    else:
        qname = normalize_qname(name)
        rdtype = dns.rdatatype.from_text(qtype)

    q = dns.message.make_query(qname, rdtype)

    try:
        if use_tcp:
            resp = dns.query.tcp(q, where=server, port=port, timeout=timeout)
        else:
            resp = dns.query.udp(q, where=server, port=port, timeout=timeout)

        if resp.rcode() != dns.rcode.NOERROR:
            print("", end="")
            return

        answers = []
        for rrset in resp.answer:
            if rrset.rdtype != rdtype:
                continue
            for item in rrset:
                answers.append(item.to_text()) # .rstrip("."))

        out = answers_to_short(answers)
        print(out or "", end="")

    except dns.exception.DNSException:
        print("", end="")

if __name__ == "__main__":
    main()
"""


def dns_lookup_on_host(
    host,
    dns_name: str,
    dns_type: str,
    server_ip: str,
    server_port: int,
    timeout_s: float = 2.0,
    use_tcp: bool = False,
) -> str | None:
    args = [
        dns_name,
        dns_type,
        server_ip,
        str(server_port),
        str(timeout_s),
        "1" if use_tcp else "0",
    ]
    quoted_args = " ".join(shlex.quote(a) for a in args)

    cmd = f"python3 - {quoted_args} <<'PY'\n" f"{REMOTE_DNS_SCRIPT}\n" f"PY"

    r = host.run(cmd)
    out = (r.stdout or "").strip()
    return out or None


def dig_python(
    host, get_vars: Dict[str, Any], domains: List[Dict[str, Any]]
) -> Tuple[bool, Dict[str, Dict[str, Any]]]:
    pdns_cfg = get_vars.get("pdns_config", {}) or {}
    local_dns_address = str(pdns_cfg.get("local-address", "127.0.0.1")).strip()
    local_dns_port = int(pdns_cfg.get("local-port", 53))

    result_state: List[Dict[str, Any]] = []

    for d in domains:
        domain = d.get("domain")
        rrtype = d.get("type", "A")
        expected = d.get("result")

        value = dns_lookup_on_host(
            host=host,
            dns_name=domain,
            dns_type=rrtype,
            server_ip=local_dns_address,
            server_port=local_dns_port,
            timeout_s=2.0,
            use_tcp=False,
        )
        output_msg = value or ""

        result_state.append(
            {
                domain: {
                    "output": output_msg,
                    "cmd": f"python3(dnspython) {rrtype} {domain} @{local_dns_address}:{local_dns_port}",
                    "failed": output_msg != expected,
                }
            }
        )

    # print(result_state)

    combined = {k: v for item in result_state for k, v in item.items()}
    failed = {
        k: v for k, v in combined.items() if isinstance(v, dict) and v.get("failed")
    }
    return (len(failed) > 0, failed)
