users:
  www-data:
    uid: 2011
    groups:
      - www-data
  auser:
    uid: 2018
    sudouser: True
    ssh_auth: ssh-rsa AUTHAUTH

  git:
    uid: 3001
    sudouser: True

  redis:
    uid: 3002

absent_users:
  - badguy
