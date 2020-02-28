#! /bin/bash

sed -r -i s/ef-rp.*/ef-rp$1/g /etc/hostname /etc/hostname
sed -r -i s/ef-rp.*/ef-rp$1/g /etc/hosts /etc/hosts
sed -r -i s/ef-rp.*/ef-rp$1/g /etc/salt/minion /etc/salt/minion
