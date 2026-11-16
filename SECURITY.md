# Security

Report suspected vulnerabilities privately to support@adspirer.com. Do not open a public issue.

The components send requests only to `https://api.adspirer.ai`, with the user's own Adspirer API
key as a Bearer token. The key is a secret input; it is redacted from error messages and is never
logged. Never commit an API key, and revoke a leaked one at https://adspirer.ai/keys.

Changes to ad accounts are off unless the flow author turns on Allow Changes. The components
never purchase or upgrade a subscription.
