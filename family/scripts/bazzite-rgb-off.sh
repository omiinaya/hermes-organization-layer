#!/usr/bin/env bash
# bazzite-rgb-off — turn off ALL RGB on the bazzite box (192.168.1.19).
# Proven 2026-09-20: i2c-12 perm + fresh server + SDK off = 9 devices dark.
# Usage: bazzite-rgb-off [off|white]
set -euo pipefail

BOX="mrx@192.168.1.19"
ACTION="${1:-off}"

case "$ACTION" in
  off)
    ssh -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no "$BOX" \
      "/opt/rgbvenv/bin/python /home/mrx/.local/bin/rgb-off-all.py"
    ;;
  white)
    ssh -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no "$BOX" \
      "/opt/rgbvenv/bin/python -c \"from openrgb import OpenRGBClient; from openrgb.utils import RGBColor; c=OpenRGBClient(address='127.0.0.1'); c.set_color(RGBColor(255,255,255)); c.show(); print('WHITE applied')\""
    ;;
  *)
    echo "usage: bazzite-rgb-off [off|white]" >&2; exit 1 ;;
esac