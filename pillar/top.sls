base:
  '*':
    - global
  'role:master':
    - match: grain
    - roles.master
  'role:redis':
    - match: grain
    - roles.redis

development:
  'environment:development':
    - match: grain
    - development

staging:
  'environment:staging':
    - match: grain
    - staging

production:
  'environment:production':
    - match: grain
    - production

