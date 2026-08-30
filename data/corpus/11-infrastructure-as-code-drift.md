# Infrastructure as Code Drift

Infrastructure as code only stays trustworthy when the live environment still matches the declared configuration. Configuration drift happens when the live cloud infrastructure no longer matches the Terraform state, which can silently reintroduce insecure settings. Drift detection helps catch manual edits, failed rollbacks, and out-of-band changes.
