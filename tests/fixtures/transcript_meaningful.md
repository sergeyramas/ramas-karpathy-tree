**User:** Помоги выбрать архитектуру для нового сервиса аутентификации. Думаю между JWT с короткими TTL и opaque tokens с Redis-based session store. Нагрузка ожидается 5000 RPS на peak, нужна возможность revocation в реалтайме.

**Assistant:** Рекомендую opaque tokens + Redis. JWT подкупает stateless природой, но revocation требует blacklist что фактически возвращает stateful behaviour. При 5000 RPS Redis справится за <1ms на lookup, операционная сложность ниже чем поддержка JWKS rotation. Главный trade-off: дополнительный round-trip к Redis на каждый request, но это <1ms vs 50ms+ network latency которую клиент уже терпит.

**User:** Принято. Какой Redis cluster setup? Sentinel или native cluster mode?

**Assistant:** Native cluster для прода, Sentinel оставь для simpler setups. Cluster даёт горизонтальное шардирование когда session pool вырастет, Sentinel только failover. Решения принять: TTL = 1 час с sliding expiry, key naming session:<userid>:<jti>, max session per user = 10.

**User:** Понял. Что с monitoring?

**Assistant:** Redis exporter для Prometheus, ключевые метрики: hit rate, eviction count, memory pressure, slowlog entries. Алерт на p99 latency > 5ms — это первый сигнал что cluster под нагрузкой.
