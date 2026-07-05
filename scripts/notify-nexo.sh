#!/usr/bin/env bash
# notify-nexo.sh — send a WhatsApp DM to the operator via wa-hub, as "GovernanceKit".
#
# Identity: the message is prefixed with "*GovernanceKit* — " so the hub's
# ensureSenderTag leaves it untouched (idempotent for already-signed text). No
# dm-alias is registered, so other projects' routing is never disturbed.
#
# Config (env or ~/.config/wa-hub/governancekit.env — see
# scripts/governancekit.env.example):
#   WA_HUB_URL   default http://localhost:8090
#   WA_HUB_KEY   required — a provisioned wa-hub client API key (X-Api-Key)
#   WA_HUB_DEST  required — operator JID, e.g. <number>@s.whatsapp.net
#
# Usage:
#   scripts/notify-nexo.sh "mensagem"
#   echo "mensagem" | scripts/notify-nexo.sh
set -euo pipefail

CONF="${WA_HUB_CONF:-$HOME/.config/wa-hub/governancekit.env}"
# shellcheck disable=SC1090
[ -f "$CONF" ] && . "$CONF"

WA_HUB_URL="${WA_HUB_URL:-http://localhost:8090}"

if [ -z "${WA_HUB_KEY:-}" ]; then
  echo "notify-nexo: WA_HUB_KEY não definido (env ou $CONF)." >&2
  exit 2
fi

if [ -z "${WA_HUB_DEST:-}" ]; then
  echo "notify-nexo: WA_HUB_DEST não definido (env ou $CONF)." >&2
  exit 2
fi

# Message from arg or stdin.
if [ "$#" -gt 0 ]; then
  MSG="$*"
else
  MSG="$(cat)"
fi
[ -n "$MSG" ] || { echo "notify-nexo: mensagem vazia." >&2; exit 2; }

# Self-identify (idempotent: skip if already signed with *...*).
case "$(printf '%s' "$MSG" | sed 's/^[[:space:]]*//')" in
  \**\**) : ;;                          # already starts with *bold*
  *) MSG="*GovernanceKit* — $MSG" ;;
esac

# Headers file (mode 600, tmp): keeps WA_HUB_KEY out of argv/`ps` — curl reads
# a header from "@file" instead of putting the secret on the command line.
hdrfile="$(mktemp)"
cleanup() {
  curl -s -m 10 -H "@$hdrfile" -H "Content-Type: application/json" \
    -X POST "$WA_HUB_URL/lock/release" >/dev/null 2>&1 || true
  rm -f "$hdrfile"
}
trap cleanup EXIT
printf 'X-Api-Key: %s\n' "$WA_HUB_KEY" > "$hdrfile"
hdr=(-H "@$hdrfile" -H "Content-Type: application/json")

# JSON-encode the message body safely.
payload="$(MSG="$MSG" DEST="$WA_HUB_DEST" python3 -c '
import json, os
print(json.dumps({"to": os.environ["DEST"], "text": os.environ["MSG"]}))')"

# acquire → send → release
curl -s -m 10 "${hdr[@]}" -X POST "$WA_HUB_URL/lock/acquire" >/dev/null 2>&1 || true

resp="$(curl -s -m 15 "${hdr[@]}" -X POST "$WA_HUB_URL/messages/send" -d "$payload")"
echo "$resp"
case "$resp" in
  *'"ok":true'*) exit 0 ;;
  *) echo "notify-nexo: envio falhou." >&2; exit 1 ;;
esac
