#!/usr/bin/env bash
set -euo pipefail
fpr=$(gpg --with-colons --auto-key-locate wkd --locate-external-keys benn@bennherrera.dev | awk -F: '/^fpr:/ {print $10; exit}')
asc=$(echo "$(dirname "${0}")"/*.asc)
set -x; gpg --assert-signer "${fpr}" --verify "${asc}" "${asc%.asc}"
