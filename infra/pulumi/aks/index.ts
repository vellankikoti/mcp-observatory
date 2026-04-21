import * as pulumi from "@pulumi/pulumi";
import * as azure from "@pulumi/azure-native";

const rg = new azure.resources.ResourceGroup("obs-aks-rg");

const cluster = new azure.containerservice.ManagedCluster("obs-aks", {
    resourceGroupName: rg.name,
    kubernetesVersion: "1.30",
    dnsPrefix: "obs-aks",
    identity: { type: "SystemAssigned" },
    agentPoolProfiles: [{
        name: "default",
        count: 2,
        vmSize: "Standard_B2s",
        mode: "System",
        osType: "Linux",
    }],
});

const creds = pulumi.all([rg.name, cluster.name]).apply(([rgName, cName]) =>
    azure.containerservice.listManagedClusterUserCredentials({
        resourceGroupName: rgName,
        resourceName: cName,
    }),
);

export const kubeconfig = creds.kubeconfigs.apply((kcs) =>
    Buffer.from(kcs[0].value, "base64").toString("utf-8"),
);
