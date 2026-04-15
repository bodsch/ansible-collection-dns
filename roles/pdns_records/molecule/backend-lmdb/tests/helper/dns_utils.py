# tests/helpers/remote_dns.py
from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

ERR_PREFIX = "__REMOTE_DNS_HELPER_ERROR__"


@dataclass(frozen=True)
class RemoteDnsLookupError(RuntimeError):
    kind: str
    message: str
    rc: int
    stderr: str

    def __str__(self) -> str:
        return f"{self.kind}: {self.message} (rc={self.rc})\n{self.stderr}".strip()


REMOTE_DNS_SCRIPT = rf"""
import sys
import json
import traceback

ERR_PREFIX = {ERR_PREFIX!r}

def fatal(code: int, kind: str, message: str, **extra):
    payload = {{
        "kind": kind,
        "message": message,
        **extra,
    }}
    sys.stderr.write(ERR_PREFIX + json.dumps(payload, ensure_ascii=False) + "\n")
    sys.exit(code)

try:
    import ipaddress
    import dns.exception
    import dns.message
    import dns.query
    import dns.rcode
    import dns.rdatatype
    import dns.reversename
except Exception as e:
    fatal(
        10,
        "import_error",
        f"{{type(e).__name__}}: {{e}}",
        traceback=traceback.format_exc(),
        hint="Install dnspython (Debian/Ubuntu: apt-get install -y python3-dnspython).",
    )

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
    if len(sys.argv) != 7:
        fatal(2, "usage_error", f"Expected 6 args, got {{len(sys.argv)-1}}: {{sys.argv[1:]}}")

    name = sys.argv[1]
    qtype = sys.argv[2].upper()
    server = sys.argv[3]
    port = int(sys.argv[4])
    timeout = float(sys.argv[5])
    use_tcp = bool(int(sys.argv[6]))

    try:
        if qtype == "PTR":
            qname = ptr_qname(name)
            rdtype = dns.rdatatype.PTR
        else:
            qname = normalize_qname(name)
            rdtype = dns.rdatatype.from_text(qtype)
    except Exception as e:
        fatal(3, "type_error", f"{{type(e).__name__}}: {{e}}", qtype=qtype)

    q = dns.message.make_query(qname, rdtype)

    try:
        if use_tcp:
            resp = dns.query.tcp(q, where=server, port=port, timeout=timeout)
        else:
            resp = dns.query.udp(q, where=server, port=port, timeout=timeout)

        rcode = resp.rcode()

        if rcode == dns.rcode.NXDOMAIN:
            print("", end="")
            return

        if rcode != dns.rcode.NOERROR:
            fatal(
                12,
                "rcode_error",
                f"RCODE={{dns.rcode.to_text(rcode)}}",
                rcode=int(rcode),
                qname=qname,
                qtype=qtype,
                server=server,
                port=port,
            )

        answers = []
        for rrset in resp.answer:
            if rrset.rdtype != rdtype:
                continue
            for item in rrset:
                # IMPORTANT: keep dig-like textual form (do NOT rstrip('.'))
                answers.append(item.to_text())

        out = answers_to_short(answers)
        print(out or "", end="")

    except dns.exception.Timeout as e:
        fatal(
            20,
            "timeout",
            f"{{type(e).__name__}}: {{e}}",
            qname=qname,
            qtype=qtype,
            server=server,
            port=port,
            timeout=timeout,
        )
    except dns.exception.DNSException as e:
        fatal(
            21,
            "dns_exception",
            f"{{type(e).__name__}}: {{e}}",
            qname=qname,
            qtype=qtype,
            server=server,
            port=port,
        )
    except Exception as e:
        fatal(
            99,
            "unexpected",
            f"{{type(e).__name__}}: {{e}}",
            traceback=traceback.format_exc(),
        )

if __name__ == "__main__":
    main()
"""


def _extract_remote_error(stderr: str) -> dict[str, Any] | None:
    m = re.search(re.escape(ERR_PREFIX) + r"(\{.*\})", stderr, flags=re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


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

    cmd = f"python3 - {quoted_args} <<'PY'\n{REMOTE_DNS_SCRIPT}\nPY"
    r = host.run(cmd)

    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()

    if getattr(r, "rc", 0) != 0:
        payload = _extract_remote_error(err) or {}
        kind = str(payload.get("kind") or "remote_error")
        msg = str(payload.get("message") or "Remote DNS helper failed")
        raise RemoteDnsLookupError(kind=kind, message=msg, rc=int(r.rc), stderr=err)

    return out or None


def _strip_final_dot(name: str) -> str:
    return name[:-1] if name.endswith(".") else name


def _norm_name(name: str) -> str:
    # DNS names are case-insensitive
    return _strip_final_dot(name.strip()).lower()


def _normalize_value(rrtype: str, value: str) -> str:
    t = rrtype.upper().strip()
    v = value.strip()

    # Single-name types
    if t in {"CNAME", "NS", "PTR"}:
        return _norm_name(v)

    # MX: "pref exchange."
    if t == "MX":
        parts = v.split()
        if len(parts) >= 2:
            pref = parts[0].strip()
            exch = _norm_name(parts[1])
            return f"{pref} {exch}"
        return v

    # SRV: "prio weight port target."
    if t == "SRV":
        parts = v.split()
        if len(parts) >= 4:
            prio, weight, port = parts[0].strip(), parts[1].strip(), parts[2].strip()
            target = _norm_name(parts[3])
            return f"{prio} {weight} {port} {target}"
        return v

    # SOA: "mname rname serial refresh retry expire minimum"
    if t == "SOA":
        parts = v.split()
        if len(parts) >= 2:
            parts[0] = _norm_name(parts[0])
            parts[1] = _norm_name(parts[1])
            return " ".join(parts)
        return v

    return v


def dns_values_equal(rrtype: str, actual: str, expected: str) -> bool:
    # allow expected to be written with/without trailing dot for name-like types
    return _normalize_value(rrtype, actual) == _normalize_value(rrtype, expected)


def dig_python(
    host,
    get_vars: Dict[str, Any],
    domains: List[Dict[str, Any]],
) -> Tuple[bool, Dict[str, Dict[str, Any]]]:
    pdns_cfg = get_vars.get("pdns_config", {}) or {}
    local_dns_address = str(pdns_cfg.get("local-address", "127.0.0.1")).strip()
    local_dns_port = int(pdns_cfg.get("local-port", 53))

    result_state: List[Dict[str, Any]] = []

    for d in domains:
        domain = d.get("domain")
        rrtype = d.get("type", "A")
        expected = d.get("result")

        error: str | None = None
        try:
            value = dns_lookup_on_host(
                host=host,
                dns_name=domain,
                dns_type=rrtype,
                server_ip=local_dns_address,
                server_port=local_dns_port,
                timeout_s=2.0,
                use_tcp=False,
            )
        except RemoteDnsLookupError as e:
            value = None
            error = str(e)

        output_msg = value or ""

        ok = False
        if expected is None:
            ok = output_msg == ""
        else:
            ok = dns_values_equal(str(rrtype), output_msg, str(expected))

        entry: Dict[str, Any] = {
            "output": output_msg,
            "cmd": f"python3(dnspython) {rrtype} {domain} @{local_dns_address}:{local_dns_port}",
            "failed": not ok,
        }
        if error:
            entry["failed"] = True
            entry["error"] = error

        result_state.append({domain: entry})

    combined = {k: v for item in result_state for k, v in item.items()}
    failed = {
        k: v for k, v in combined.items() if isinstance(v, dict) and v.get("failed")
    }
    return (len(failed) > 0, failed)


def extract_error(failed: dict[str, dict[str, Any]]) -> list[str]:
    """ """
    seen: set[str] = set()

    for _, info in failed.items():
        err = info.get("failed")
        if err:
            seen.add(info.get("cmd"))

    return seen


def extract_unique_errors(failed: dict[str, dict[str, Any]]) -> list[str]:
    """
    Extracts `error` strings from a molecule-style `failed` dict and removes duplicates
    while preserving first-seen order.

    It also normalizes the remote helper error format:
      "<summary line>\\n__REMOTE_DNS_HELPER_ERROR__{json...}"
    into a short, stable message (kind/message + optional hint).
    """
    seen: set[str] = set()
    unique: list[str] = []

    for _, info in failed.items():
        err = info.get("error")
        if not isinstance(err, str) or not err.strip():
            continue

        normalized = _normalize_error_text(err)
        if normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)

    return unique


def _normalize_error_text(err: str) -> str:
    err = err.strip()

    # If the remote helper JSON marker is present, prefer the JSON payload (stable & dedup-friendly).
    if ERR_PREFIX in err:
        _, payload = err.split(ERR_PREFIX, 1)
        payload = payload.strip()

        try:
            data = json.loads(payload)
            kind = str(data.get("kind") or "remote_error")
            message = str(data.get("message") or "").strip()
            hint = data.get("hint")
            parts = [f"{kind}: {message}".strip()]
            if isinstance(hint, str) and hint.strip():
                parts.append(f"hint: {hint.strip()}")
            return "\n".join(parts).strip()
        except Exception:
            # Fall back to raw error text if JSON parsing fails
            return err

    return err
