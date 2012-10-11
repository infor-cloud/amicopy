#!/bin/sh
set -x; set -e
cd /media/ephemeral0
wget --no-check-certificate '%(tsunami)s' -O tsunami ; chmod +x tsunami

cat > secret.txt << 'EOF'
%(secret)s
EOF
    
until nc -z %(source)s 46224 > /dev/null ; do
    sleep 30
done

for DEV in /dev/xvd[f-p] ; do
    BASE=`basename "$DEV"`
    ./tsunami set rateadjust yes connect %(source)s get "$BASE".img \
            get "$BASE".img.sha1 exit || true
done

for DEV in /dev/xvd[f-p] ; do
    BASE=`basename "$DEV"`
    sha1sum -c "$BASE".img.sha1
    dd if="$BASE".img bs=1M | openssl enc -d -aes-128-cbc \
            -pass file:secret.txt > "$DEV"
done

halt
