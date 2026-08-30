# Kubernetes Network Policy

Kubernetes network policy is a namespace-level control for limiting lateral movement inside a cluster. A Kubernetes network policy restricts which pods can talk to each other, so a compromised pod cannot reach services it was never meant to contact. It complements service mesh policy and cloud firewalls rather than replacing them.
