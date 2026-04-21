# Ephemeral cloud-K8s stacks

These Pulumi stacks are used by `.github/workflows/cluster-matrix.yml` to spin
managed EKS, GKE, and AKS clusters on demand, run the golden + integration +
mcp_contract suites against each, then tear them down.

## Prerequisites

Required GitHub Actions secrets:
- `PULUMI_ACCESS_TOKEN`
- AWS: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- GCP: `GCP_CREDENTIALS` (JSON service-account key), `GCP_PROJECT`
- Azure: `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`

## Local use

```bash
cd infra/pulumi/eks
pulumi stack init local
pulumi up
pulumi stack output kubeconfig --show-secrets > /tmp/obs-eks-kubeconfig
KUBECONFIG=/tmp/obs-eks-kubeconfig uv run pytest -m "golden or integration or mcp_contract"
pulumi destroy
```

## Cost warning

Each run provisions real cloud resources. `workflow_dispatch` is the only push
trigger; the `schedule` fires once per week (Monday 07:00 UTC). Teardown happens
in the workflow's `always()` step but failed runs can leave orphans — audit
Pulumi state regularly to avoid unexpected charges.

Estimated cost per full matrix run (all 3 clouds): ~$2-5 USD depending on runtime.
