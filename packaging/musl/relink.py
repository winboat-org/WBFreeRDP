#!/usr/bin/env python3
"""Relink the portable client using the supplied archives and object files."""
# SPDX-License-Identifier: Apache-2.0
import argparse
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=Path('xfreerdp-relinked'))
args = parser.parse_args()
kit = Path(__file__).resolve().parent
metadata = json.loads((kit / 'link.json').read_text())
arguments = [str(kit / 'root' / arg['input'].lstrip('/')) if isinstance(arg, dict) else arg
             for arg in metadata['arguments']]
# Give GCC the shipped musl startup files and runtime archives before its defaults.
arguments += ['-B' + str(kit / 'root/usr/lib') + '/', '-L' + str(kit / 'root/usr/lib')]
subprocess.run(['cc', *arguments, '-o', str(args.output.resolve())], check=True)
print(args.output.resolve())
