#!/bin/sh
set -x; set -e
cd /media/ephemeral0
wget --no-check-certificate '%(tsunamid)s' -O tsunamid ; chmod +x tsunamid

cat > secret.txt << 'EOF'
%(secret)s
EOF

for DEV in /dev/xvd[f-p] ; do
    BASE=`basename "$DEV"`
    dd if="$DEV" bs=1M | openssl enc -e -aes-128-cbc -pass file:secret.txt \
            > "$BASE".img
    sha1sum "$BASE".img > "$BASE".img.sha1
done

./tsunamid --hbtimeout 600 > tsunamid.log
