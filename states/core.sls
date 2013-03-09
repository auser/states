include:
  {% if grains['os'] == 'Ubuntu' %}
  - apt
  {% endif %}
  - iptables
  - users
  - ssh
  - logrotate
  - salt.minion
  - git

curl:
  pkg:
    - installed

build-essential:
  pkg:
    - installed
