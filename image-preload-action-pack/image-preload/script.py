# Copyright (c) 2022 Arista Networks, Inc.
# Use of this source code is governed by the Apache License 2.0
# that can be found in the COPYING file.

# Note: This script will become obsolete once the image studio system
# becomes available, after which this only serves as an example of script writing

from urllib.parse import urljoin

authority = ctx.changeControl.args.get("authority")
path = ctx.changeControl.args.get("path")
eos = ctx.changeControl.args.get("eos")
vrf = ctx.changeControl.args.get("vrf")
imageUrl = urljoin(f"https://{authority}", path + eos)

ctx.alog(f"Downloading EOS image from {imageUrl}")
cmds = [
    "enable",
    f"cli vrf {vrf}",
    f"copy {imageUrl} flash:",
]
cmdResponses: list[dict] = ctx.runDeviceCmds(cmds)
# Iterate through the list of responses for the commands, and if an error occurred in
# any of the commands, raise an exception
# Only consider the first error that is encountered as following commands require previous ones to succeed
errs = [resp.get('error') for resp in cmdResponses if resp.get('error')]
if errs:
    raise UserWarning(f"Preloading image failed with: {errs[0]}")
ctx.alog("Downloading of Eos image completed successfully")
