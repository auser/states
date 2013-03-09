#!/bin/bash

HOSTNAME=${1:-minion}
SALT_MASTER=${2:-192.168.98.11}
ENV=${3:-development}

echo "------> Bootstrapping minion $HOSTNAME (master: $SALT_MASTER) for environment $ENV"

__apt_get_noinput() {
    apt-get install -y -o DPkg::Options::=--force-confold $@
}

apt-get update
__apt_get_noinput python-software-properties curl debconf-utils
apt-get update

# Set the hostname
echo """
127.0.0.1       localhost
127.0.1.1       $HOSTNAME
$SALT_MASTER    saltmaster
""" > /etc/hosts
echo "$HOSTNAME" > /etc/hostname
hostname `cat /etc/hostname`

# We're using the saltstack canonical bootstrap method here to stay with the
# latest open-source efforts
#
# Eventually, we can come to settle down on our own way of bootstrapping
\curl -L http://bootstrap.saltstack.org | sudo sh -s -- stable

# Set salt master location and start minion
echo """
master: saltmaster
id: $HOSTNAME
grains:
  environment: $ENV
""" > /etc/salt/minion

salt-call -g >> /dev/null 2>&1 &

echo "------> The minion is booted and waiting for approval
Log in to the master machine and accept the key"

