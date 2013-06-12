include:
  - git

## Get redis
get-redis:
  file.managed:
    - name: /usr/src/redis-stable.tar.gz
    - source: http://download.redis.io/redis-stable.tar.gz
    - source_hash: sha1=c12d48eeeb2f8eaf08b87d4f56cacea311a49a50
  cmd.wait:
    - cwd: /usr/src
    - names:
      - tar -zxvf redis-stable.tar.gz
    - watch:
      - file: redis
      
redis-init-script:
  file.managed:
    - name: /etc/init/redis.conf
    - template: jinja
    - mode: 0750
    - user: {{ pillar['redis']['user'] }}
    - group: {{ pillar['redis']['group'] }}
    - context:
        name: redis
        user: {{ pillar['redis']['user'] }}
    - require:
      - file: get-redis

redis:
  file:
    - name: /etc/redis/redis.conf
    - managed
    - template: jinja
    - source: salt://redis/templates/redis.conf.jinja
    - require:
      - file: redis-init-script
  service:
    - running
    - require:
      - file: redis-init-script
      - file: redis
