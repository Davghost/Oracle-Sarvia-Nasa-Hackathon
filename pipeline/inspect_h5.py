"""Print the structure of an HDF5 file (T37). Reads metadata only, plus tiny 1D/scalar datasets.

Usage:  python pipeline/inspect_h5.py data/<file>.h5 > docs/h5_structure.txt
Needs:  pip install h5py
Assumes nothing about the NISAR layout: it just walks the whole file.
"""
import sys

import h5py
import numpy as np

MAX_ATTR_CHARS = 140


def short(v):
    if isinstance(v, bytes):
        v = v.decode("utf-8", "replace")
    if isinstance(v, np.ndarray):
        v = v.tolist() if v.size <= 8 else f"<array shape={v.shape} dtype={v.dtype}>"
    s = str(v)
    return s if len(s) <= MAX_ATTR_CHARS else s[:MAX_ATTR_CHARS] + "..."


def show_attrs(obj, indent):
    for k, v in obj.attrs.items():
        try:
            print(f"{indent}  @{k} = {short(v)}")
        except Exception as e:  # unreadable attribute
            print(f"{indent}  @{k} = <unreadable: {e}>")


def describe_dataset(name, ds, indent):
    line = f"{indent}[D] {name}  shape={ds.shape} dtype={ds.dtype}"
    if ds.chunks:
        line += f" chunks={ds.chunks}"
    if ds.compression:
        line += f" compression={ds.compression}"
    print(line)
    try:
        if ds.shape == ():
            print(f"{indent}  value = {short(ds[()])}")
        elif ds.ndim == 1 and 0 < ds.size <= 100000:
            a = ds[()]
            if np.issubdtype(a.dtype, np.number):
                step = float(a[1] - a[0]) if a.size > 1 else None
                print(f"{indent}  first={a[0]} last={a[-1]} n={a.size} step={step}")
            else:
                print(f"{indent}  values[:3] = {[short(x) for x in a[:3]]}")
    except Exception as e:
        print(f"{indent}  <could not read: {e}>")
    show_attrs(ds, indent)


def walk(group, path="/", depth=0):
    indent = "  " * depth
    for name in sorted(group.keys()):
        item = group[name]
        full = f"{path.rstrip('/')}/{name}"
        if isinstance(item, h5py.Group):
            print(f"{indent}[G] {full}")
            show_attrs(item, indent)
            walk(item, full, depth + 1)
        elif isinstance(item, h5py.Dataset):
            describe_dataset(full, item, indent)


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    with h5py.File(sys.argv[1], "r") as f:
        print(f"FILE {sys.argv[1]}")
        show_attrs(f, "")
        walk(f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
