import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";
import * as eks from "@pulumi/eks";

const cluster = new eks.Cluster("obs-eks", {
    version: "1.30",
    instanceType: "t3.medium",
    desiredCapacity: 2,
    minSize: 1,
    maxSize: 3,
    createOidcProvider: false,
    providerCredentialOpts: { profileName: aws.config.profile },
});

export const kubeconfig = cluster.kubeconfig;
