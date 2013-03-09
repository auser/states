sudo:
  group:
    - present
    - system: True
  pkg:
    - installed
    - require:
      - group: sudo
      - file: /etc/sudoers.d

/etc/sudoers.d:
  file:
    - directory
    - clean: True

sudoer-defaults:
    file.append:
        - name: /etc/sudoers
        - require:
          - pkg: sudo
        - text:
          - Defaults    !secure_path

