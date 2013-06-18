redis:
  port: 6379
  user: redis
  group: redis

  maxmemory: 2G
  maxmemory-policy: allkeys-lru
