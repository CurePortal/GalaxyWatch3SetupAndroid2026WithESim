#!/usr/bin/python3
"""Minimal Tizen sdb client.

Implements the SDB packet protocol and the ADB-style RSA authentication used by
Tizen's sdbd. Useful when a vendor sdb binary is blocked by the host OS network
permissions, or when you want scripted access to a watch.

Signing: RSA PKCS#1 v1.5 over SHA1-DigestInfo || token, with no extra hashing
(the openssl CLI is used for key generation and signing).

Usage:
    ./watchsdb.py <watch-ip> [command]

Environment:
    SDB_KEY   path to the RSA host key (default: ~/.tizen-sdb-key.pem)
"""
import base64
import os
import socket
import struct
import subprocess
import sys

KEY = os.path.expanduser(os.environ.get("SDB_KEY", "~/.tizen-sdb-key.pem"))

CNXN = 0x4E584E43
AUTH = 0x48545541
OPEN = 0x4E45504F
OKAY = 0x59414B4F
CLSE = 0x45534C43
WRTE = 0x45545257

HOST_VERSION = 0x01000000
HOST_MAX_DATA = 0x40000
MAX_PACKET = 1 << 20

AUTH_TOKEN = 1
AUTH_SIGNATURE = 2
AUTH_PUBLIC_KEY = 3

SHA1_DIGEST_INFO = bytes([0x30, 0x21, 0x30, 0x09, 0x06, 0x05, 0x2b, 0x0e,
                          0x03, 0x02, 0x1a, 0x05, 0x00, 0x04, 0x14])


def ensure_key():
    """Create the RSA host key on first use."""
    if not os.path.exists(KEY):
        os.makedirs(os.path.dirname(os.path.expanduser(KEY)) or ".", exist_ok=True)
        subprocess.run(["openssl", "genrsa", "-out", KEY, "2048"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return KEY


def key_numbers():
    """Return (modulus, exponent) of the host key."""
    out = subprocess.run(["openssl", "rsa", "-in", KEY, "-noout", "-modulus"],
                         check=True, capture_output=True, text=True).stdout.strip()
    n = int(out.split("=", 1)[1], 16)
    txt = subprocess.run(["openssl", "rsa", "-in", KEY, "-noout", "-text"],
                         check=True, capture_output=True, text=True).stdout
    e = 65537
    for line in txt.splitlines():
        if "publicExponent" in line:
            raw = line.split(":", 1)[1].strip()
            e = int(raw, 16) if raw.startswith("0x") else 65537
    return n, e


def sign_token(token):
    """RSA PKCS#1 v1.5 signature over SHA1-DigestInfo || token (no extra hash)."""
    data = SHA1_DIGEST_INFO + token
    p = subprocess.run(["openssl", "pkeyutl", "-sign", "-inkey", KEY,
                        "-pkeyopt", "rsa_padding_mode:pkcs1"],
                       input=data, capture_output=True, check=True)
    return p.stdout


def public_key_blob(name="host@tizen-sdb"):
    """Android RSAPublicKey struct, base64, space, name, NUL."""
    n, e = key_numbers()
    mod_bytes = 2048 // 8
    r = 1 << 2048
    rr = (r * r) % n
    n0inv = (-pow(n % (1 << 32), -1, 1 << 32)) % (1 << 32)
    le = lambda v: v.to_bytes(mod_bytes, "little")
    struct_bytes = struct.pack("<II", mod_bytes // 4, n0inv) + le(n) + le(rr) + struct.pack("<I", e)
    b64 = base64.b64encode(struct_bytes).decode()
    return (b64 + " " + name + "\0").encode()


def encode(cmd, a0, a1, data=b""):
    return struct.pack("<IIIIII", cmd, a0, a1, len(data), sum(data) & 0xFFFFFFFF,
                       cmd ^ 0xFFFFFFFF) + data


def read_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise EOFError("connection closed")
        buf += chunk
    return buf


def read_packet(sock):
    hdr = read_exact(sock, 24)
    cmd, a0, a1, length, csum, magic = struct.unpack("<IIIIII", hdr)
    if magic != (cmd ^ 0xFFFFFFFF):
        raise IOError("bad packet magic")
    if length < 0 or length > MAX_PACKET:
        raise IOError("bad packet length %d" % length)
    data = read_exact(sock, length) if length else b""
    return cmd, a0, a1, data


class Sdb:
    def __init__(self, host, port=26101, confirm_timeout=120):
        self.sock = socket.create_connection((host, port), 10)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.next_id = 1
        self.max_data = 4096
        self._handshake(confirm_timeout)

    def _send(self, cmd, a0, a1, data=b""):
        self.sock.sendall(encode(cmd, a0, a1, data))

    def _handshake(self, confirm_timeout):
        self.sock.settimeout(15)
        self._send(CNXN, HOST_VERSION, HOST_MAX_DATA, b"host::\0")
        cmd, a0, a1, data = read_packet(self.sock)
        signed = False
        key_sent = False
        while cmd == AUTH and a0 == AUTH_TOKEN:
            if not signed:
                self._send(AUTH, AUTH_SIGNATURE, 0, sign_token(data))
                signed = True
            elif not key_sent:
                self._send(AUTH, AUTH_PUBLIC_KEY, 0, public_key_blob())
                key_sent = True
                print("[sdb] key sent - TAP ALLOW ON THE WATCH", file=sys.stderr, flush=True)
                self.sock.settimeout(confirm_timeout)
            else:
                raise IOError("watch rejected the key")
            cmd, a0, a1, data = read_packet(self.sock)
        if cmd != CNXN:
            raise IOError("unexpected handshake reply 0x%08x" % cmd)
        self.banner = data.decode("ascii", "replace").strip("\0 ")
        if a1 > 0:
            self.max_data = min(a1, HOST_MAX_DATA)

    def _open(self, service):
        local = self.next_id
        self.next_id += 1
        self._send(OPEN, local, 0, service.encode() + b"\0")
        while True:
            cmd, a0, a1, data = read_packet(self.sock)
            if a1 != local:
                continue
            if cmd == OKAY:
                return local, a0
            raise IOError("service %r refused" % service)

    def shell(self, command):
        local, remote = self._open("shell:" + command)
        out = b""
        self.sock.settimeout(120)
        while True:
            cmd, a0, a1, data = read_packet(self.sock)
            if a1 != local:
                continue
            if cmd == WRTE:
                out += data
                self._send(OKAY, local, remote)
            elif cmd == CLSE:
                self._send(CLSE, local, remote)
                break
            elif cmd == OKAY:
                continue
        return out.decode("utf-8", "replace")

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


def main():
    if len(sys.argv) < 2:
        print("usage: %s <watch-ip> [command]" % os.path.basename(sys.argv[0]),
              file=sys.stderr)
        sys.exit(2)
    host = sys.argv[1]
    command = sys.argv[2] if len(sys.argv) > 2 else "id"
    ensure_key()
    s = Sdb(host)
    print("[sdb] banner:", s.banner)
    print(s.shell(command))
    s.close()


if __name__ == "__main__":
    main()
