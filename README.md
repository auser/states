## Saltstack states

### What?

A collection of states that I use when building my salt stacks.

### States

#### Users

The user state picks up the pillar user data. If specified, it will set:

    uid
    gid
    groups
    ssh_auth
    sudouser
    fullname


