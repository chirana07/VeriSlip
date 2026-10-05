# Staging deployment

VeriSlip's staging pipeline targets Render using the repository Dockerfile.
`render.yaml` declares the service, its public `/health` probe, non-sensitive
defaults, and placeholders for secrets. Render auto-deploy is disabled so the
GitHub workflow deploys only after `CI` succeeds on `main` or an authorized
manual dispatch is run.

## One-time setup

1. In Render, create a Blueprint from this repository and select the staging
   service declared in `render.yaml`.
2. Set `VERISLIP_API_KEY_HASHES` in the Render dashboard to the JSON mapping of
   SHA-256 API-key hashes and tiers. Never enter raw API keys in repository
   files. Leave unused integration secrets blank; configure WhatsApp, Shopify,
   or SMS only when that integration is being tested.
3. Create a Render deploy hook for `verislip-staging`.
4. Create a GitHub environment named `staging`. Add the hook as the encrypted
   secret `RENDER_STAGING_DEPLOY_HOOK_URL` and the public HTTPS service origin
   as the variable `VERISLIP_STAGING_URL` (without a trailing slash).
5. Apply required reviewers to the GitHub environment if deployments need an
   approval gate.

The deploy workflow has read-only repository permission, never prints the hook,
uses bounded HTTP timeouts, and verifies that `/health` returns the expected
healthy payload. When staging secrets are not yet configured in the repository,
automatic runs gracefully skip deployment to keep CI green, while explicit manual
dispatches validate configuration and report missing values. Application
credentials remain exclusively in Render's secret store.

## Deployment and verification

Merging a CI-green commit to `main` triggers staging. An authorized maintainer
can also run **Deploy staging** from GitHub Actions. Verify:

```cmd
curl --fail https://YOUR-STAGING-HOST.example/health
curl --fail -H "X-API-Key: YOUR-STAGING-KEY" https://YOUR-STAGING-HOST.example/api/v1/verifications/history
```

The second request should authenticate; an empty history response is normal for
a new staging service. Do not use production merchant data or credentials.

## Rollback and troubleshooting

If the health gate fails, inspect Render logs for the correlation ID and error
type, not uploaded content. Roll back from Render's **Deploys** page to the last
healthy image, or revert the faulty commit and rerun the workflow. Rotate the
deploy hook immediately if it is exposed. A local in-memory store is acceptable
for smoke testing but resets on restart; attach managed Redis/persistent stores
before multi-instance or durable beta use.

The initial blueprint does not provision paid infrastructure automatically.
The `starter` plan and Singapore region are explicit defaults that maintainers
may adjust during Blueprint creation based on project budget and availability.
