# OpenShift Service Mesh 3 (Istio) on this cluster

Installs **Red Hat OpenShift Service Mesh 3** — the Istio-based mesh using the
upstream **Sail operator** (`sailoperator.io` API: `Istio`, `IstioCNI`, …), not
the older Service Mesh 2 / Maistra `ServiceMeshControlPlane`.

| Thing | Value |
|-------|-------|
| Operator | `servicemeshoperator3` (Red Hat), channel `stable` → **v3.4.2** |
| Istio version | **v1.30.4** |
| Control plane ns | `istio-system` (istiod) |
| CNI ns | `istio-cni` (required on OpenShift) |
| Update strategy | `InPlace` |

## Manifests (`openshift/servicemesh/`)

| File | Creates |
|------|---------|
| `01-subscription.yaml` | SM3 operator Subscription (cluster-wide via `global-operators` OG) |
| `02-namespaces.yaml` | `istio-cni`, `istio-system` |
| `03-istio-cni.yaml` | `IstioCNI/default` |
| `04-istio.yaml` | `Istio/default` control plane |
| `install.sh` / `uninstall.sh` | apply/teardown with readiness waits |

## Install / verify / teardown

```bash
cd openshift/servicemesh
./install.sh

oc get istio,istiocni                 # both Healthy/Ready
oc get pods -n istio-system           # istiod Running
oc get pods -n istio-cni              # istio-cni-node DaemonSet Running

./uninstall.sh          # remove mesh
./uninstall.sh --all    # also remove the operator
```

## Adding workloads to the mesh

The mesh starts **empty**. To enroll a namespace and inject sidecars:

```bash
oc label namespace <ns> istio-injection=enabled
oc rollout restart deployment -n <ns>     # so pods get the Envoy sidecar
```

(Because `updateStrategy` is `InPlace` with the default revision named `default`,
the simple `istio-injection=enabled` label works. With RevisionBased updates you'd
use `istio.io/rev=<revision>` instead.)

## Optional add-ons (not installed)
- **Kiali** — console/observability (`kiali-ossm` operator + a `Kiali` CR).
- **Distributed tracing** — Tempo (`tempo-product`) + OpenTelemetry Collector.
- **Ingress gateway** — a `Gateway` (Gateway API) or an injected gateway Deployment.

Ask if you want any of these wired in.
