import * as pulumi from "@pulumi/pulumi";
import * as gcp from "@pulumi/gcp";

const cluster = new gcp.container.Cluster("obs-gke", {
    location: "us-central1-a",
    initialNodeCount: 2,
    nodeConfig: { machineType: "e2-standard-2" },
    deletionProtection: false,
    minMasterVersion: "1.30",
});

export const kubeconfig = pulumi.all([cluster.name, cluster.endpoint, cluster.masterAuth]).apply(
    ([name, endpoint, auth]) => `apiVersion: v1
clusters:
- cluster:
    certificate-authority-data: ${auth.clusterCaCertificate}
    server: https://${endpoint}
  name: ${name}
contexts:
- context:
    cluster: ${name}
    user: ${name}
  name: ${name}
current-context: ${name}
kind: Config
users:
- name: ${name}
  user:
    exec:
      apiVersion: client.authentication.k8s.io/v1beta1
      command: gke-gcloud-auth-plugin
      installHint: "Install gke-gcloud-auth-plugin"
      provideClusterInfo: true
`,
);
