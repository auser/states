include:
  - users.sudo

{% for name, user in pillar.get('users', {}).items() %}
{% set home = user.get('home', "/home/%s" % name) %}

{% for group in user.get('groups', []) %}
{{ group.name }}_group:
  group:
    - name: {{ group.name }}
    {% if group.gid is defined %}
    - gid: {{ group.gid }}
    {% endif %}
    - present
{% endfor %}

{{ name }}_user:
  file.directory:
    - name: {{ home }}
    - user: {{ name }}
    - group: {{ name }}
    - mode: 0755
  user.present:
    - name: {{ name }}
    - home: {{ home }}
    - shell: {{ pillar.get('unprivileged_shell', '/bin/bash') }}
    - uid: {{ user['uid'] }}
    - gid_from_name: True
    {% if 'fullname' in user %}
    - fullname: {{ user['fullname'] }}
    {% endif %}
    {% if user.get('groups', [])|length > 0 %}
    - groups:
      {% for group in user.get('groups', []) %}
        - {{ group.name }}
      {% endfor %}
    - require:
        - file: {{ name }}_user
      {% for group in user.get('groups', []) %}
        - group: {{ group.name }}_group
      {% endfor %}
    {% endif %}
  {% if 'ssh_auth' in user %}
  ssh_auth:
    - present
    - user: {{ name }}
    - name: {{ user['ssh_auth'] }}
    - require:
        - file: {{ name }}_user
        - user: {{ name }}_user
  {% endif %}

{% if 'sudouser' in user %}
sudoer-{{ name }}:
    file.append:
        - name: /etc/sudoers
        - text:
          - "{{ name }}    ALL=(ALL)  NOPASSWD: ALL"
        - require:
          - file: sudoer-defaults

{% endif %}

{% endfor %}

{% for user in pillar.get('absent_users', []) %}
{% if user is defined %}
{{ user }}:
  user.absent
{% endif %}
{% endfor %}
