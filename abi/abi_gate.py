#!/usr/bin/env python3
"""Exact ABI gate for the Satetsu Shigure X6882 kernel.

Usage:
    abi_gate.py <vmlinux.symvers> <kernel_required.tsv> <abi_gki_aarch64.xml> [module_layout]

Three checks, all exact:

1. Every symbol in kernel_required.tsv must be exported by the kernel with the
   CRC the vendor modules were built against. A missing symbol is an
   unresolvable import at module load time; a mismatched CRC would need
   CONFIG_MODULE_FORCE_LOAD and would taint the kernel.
2. module_layout must equal the expected value (0x7c24b32d on this device).
3. Full frozen-KMI parity: every symbol of the ABI description shipped in the
   ACK tree that this build exports must carry the same CRC. A mismatch means
   some Kconfig option or patch changed a type reachable from an exported
   symbol, even if no current module imports it.

Exit status 0 only if all three pass.
"""

import re
import sys


def norm_crc(value):
    """Compare CRCs numerically: the XML omits leading zeros (0xb175f0a)
    while Module.symvers always pads to eight digits (0x0b175f0a)."""
    try:
        return int(value, 16)
    except (TypeError, ValueError):
        return value


def load_symvers(path):
    have = {}
    with open(path, errors="replace") as fh:
        for line in fh:
            fields = line.rstrip("\n").split("\t")
            if len(fields) >= 2 and fields[1].strip():
                have[fields[1].strip()] = norm_crc(fields[0].strip().lower())
    return have


def load_tsv(path):
    want = {}
    with open(path, errors="replace") as fh:
        for line in fh:
            if line.startswith("#") or not line.strip():
                continue
            fields = line.split("\t")
            if len(fields) >= 2 and fields[1].strip().startswith("0x"):
                want[fields[0].strip()] = norm_crc(fields[1].strip().lower())
    return want


def load_kmi(path):
    kmi = {}
    with open(path, errors="replace") as fh:
        text = fh.read()
    for m in re.finditer(r"<elf-symbol name='([^']+)'[^>]*crc='([^']+)'", text):
        kmi[m.group(1)] = norm_crc(m.group(2).lower())
    return kmi


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    symvers, kreq, kmi_xml = sys.argv[1:4]
    expected_layout = norm_crc(
        (sys.argv[4] if len(sys.argv) > 4 else "0x7c24b32d").lower())

    have = load_symvers(symvers)
    want = load_tsv(kreq)
    kmi = load_kmi(kmi_xml)

    print("kernel exports: %d" % len(have))
    print("kernel-required vendor imports: %d" % len(want))
    print("of the 2462 vendor imports, %d are exported by the vendor modules "
          "themselves, not by the kernel." % (2462 - len(want)))

    rc = 0
    ok = bad = miss = 0
    for sym in sorted(want):
        got = have.get(sym)
        if got is None:
            miss += 1
            if miss <= 30:
                print("MISSING   %-42s expected 0x%08x" % (sym, want[sym]))
        elif got == want[sym]:
            ok += 1
        else:
            bad += 1
            if bad <= 30:
                print("MISMATCH  %-42s expected 0x%08x got 0x%08x"
                      % (sym, want[sym], got))
    print("VENDOR ABI: required=%d crc_ok=%d crc_mismatch=%d missing=%d"
          % (len(want), ok, bad, miss))

    if have.get("module_layout") != expected_layout:
        print("FAIL: module_layout is 0x%08x, expected 0x%08x"
              % (have.get("module_layout"), expected_layout))
        rc = 1
    if bad or miss:
        rc = 1

    k_bad = [(s, c, have[s]) for s, c in kmi.items()
             if s in have and have[s] != c]
    k_miss = [s for s in kmi if s not in have]
    k_ok = sum(1 for s, c in kmi.items() if have.get(s) == c)
    print("KMI PARITY: kmi=%d crc_ok=%d crc_mismatch=%d absent=%d"
          % (len(kmi), k_ok, len(k_bad), len(k_miss)))
    for sym, crc, got in k_bad[:30]:
        print("KMI BAD    %-42s expected 0x%08x got 0x%08x"
              % (sym, crc, got))
    for sym in sorted(k_miss)[:20]:
        print("KMI ABSENT %s" % sym)
    if k_bad:
        rc = 1

    if rc == 0:
        print("RESULT: exact vendor ABI parity")
    else:
        print("RESULT: NOT ABI-compatible")
    return rc


if __name__ == "__main__":
    sys.exit(main())
