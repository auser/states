include:
  - ssh.client
  - users

git:
  pkg.installed:
    {% if grains['os'] == 'Ubuntu' %}
    - name: git-core
    {% else -%}
    - name: git
    {% endif -%}
    - require:
      - pkg: openssh-client
      - file: sudoer-defaults