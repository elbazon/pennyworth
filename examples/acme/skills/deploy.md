---
name: deploy
description: Use before deploying or rolling back an Acme service — the deploy steps, health checks, and rollback.
---

# Deploying an Acme service

1. Run the test suite and the build.
2. Deploy to staging; confirm the health endpoint is green.
3. Promote to production; watch error rates for ten minutes.
4. To roll back, re-deploy the previous tag and confirm health.
