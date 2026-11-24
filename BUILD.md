# Satetsu Shigure — GKI 5.10 for Infinix Hot 50 4G (X6882 / MT6789)

This repository is a **build control plane**, not a kernel source tree.

The kernel is compiled from a pristine AOSP ACK `android12-5.10-lts` tarball,
pinned by commit id in `.github/workflows/build-kernel.yml`. Only these paths
are used:

| path | role |
|---|---|
| `.github/workflows/build-kernel.yml` | fetch, configure, build, gate, package |
| `arch/arm64/configs/performance.fragment` | the only config delta over `gki_defconfig` |
| `patches/` | minimal source patches (currently one: `STACKPROTECTOR_PER_TASK=n`) |
| `abi/abi_gate.py` | exact CRC gate, run before anything is packaged |
| `abi/x6882_kernel_required.tsv` | 1,395 symbols the vendor modules import from the kernel |
| `abi/x6882_vendor_crcs_loaded.tsv` | all 2,462 imports of the 186 loaded modules |

The kernel sources checked in at the repository root are the old Zenithed
`android12-5.10-rebased` tree. **They are not built.** That base patches 260
files, changes struct layouts and produced 814 CRC mismatches against this
device's modules (`module_layout 0x1da8fe35` instead of `0x7c24b32d`). It is
kept only for history.

## Why pristine ACK

The device's own KMI description, `android/abi_gki_aarch64.xml`, agrees with
the vendor modules' import table on 1,397/1,397 overlapping symbols. A plain
`gki_defconfig` build of ACK 5.10.274 reproduces the vendor CRCs exactly, so no
MediaTek-derived tree is needed:

```
VENDOR ABI: required=1395 crc_ok=1395 crc_mismatch=0 missing=0
KMI PARITY: kmi=7298 crc_ok=7298 crc_mismatch=0 absent=0
module_layout 0x7c24b32d
```

## Build

Trigger from the Actions tab (`workflow_dispatch`) or push a `v5.10-satetsu*`
tag. A tag also publishes a GitHub release with the zip attached.

Each run:

1. fetches `+archive/<ACK_COMMIT>.tar.gz` (no `.git`, so the release string is
   clean) into `/home/runner/kernel`, outside the checkout workspace —
   `scripts/setlocalversion` walks *up* and would otherwise append `-g<sha>`;
2. applies `performance.fragment` over `gki_defconfig`;
3. builds `Image` with clang-18, ThinLTO and CFI;
4. asserts `5.10.274-android12-9-Satetsu-Shigure` exactly;
5. runs `abi/abi_gate.py` on `out/vmlinux.symvers` — a single CRC difference
   fails the run, before packaging;
6. packages AnyKernel3 (`BLOCK=boot`, `IS_SLOT_DEVICE=auto`, `do.modules=0`)
   and writes `<zip>.sha256`.

## ABI rules for future edits

`genksyms` hashes every type reachable from an exported symbol, so any Kconfig
option that adds or removes a struct member changes CRCs even though the source
is untouched. Measured example: `CONFIG_TRANSPARENT_HUGEPAGE=n` removes members
from `struct page` and moves `__alloc_pages_nodemask` from `0xcfd14bde` to
`0x0407c052`.

Therefore:

- only settings that cannot change a type go in `performance.fragment`;
- type-affecting options stay at their `gki_defconfig` values and are asserted
  in the workflow instead;
- `CONFIG_LOCALVERSION_AUTO` must stay `y` (`MODULE_SCMVERSION` depends on it);
- after any change, the gate must still print `RESULT: exact vendor ABI parity`.

`CONFIG_MODULE_FORCE_LOAD=y` is a safety net only. It downgrades a CRC mismatch
to a taint; it does not fix a layout difference, and it must never be the
reason a run passes.

## Verify a downloaded artifact

```sh
sha256sum -c Satetsu-Shigure-X6882-GKI510-v5.10-satetsu-<UTC>.zip.sha256
unzip -tq Satetsu-Shigure-X6882-GKI510-v5.10-satetsu-<UTC>.zip
unzip -p Satetsu-Shigure-X6882-GKI510-v5.10-satetsu-<UTC>.zip Image | sha256sum
```

The last hash must equal the `Image` in the same workflow artifact.
