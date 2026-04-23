#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAMESPACE="${NAMESPACE:-vault-demo}"
DEPLOYMENT="${DEPLOYMENT:-python-vault-app}"
SERVICE_MANIFEST="${SERVICE_MANIFEST:-$ROOT_DIR/k8s/oracle-host-service.yaml}"

echo "==> Applying ExternalName Service so oracle-host resolves inside Kubernetes"
kubectl apply -f "$SERVICE_MANIFEST"

echo
echo "==> Showing the service we just applied"
kubectl get service oracle-host -n "$NAMESPACE" -o wide

echo
echo "==> Confirming the service is an ExternalName alias to host.docker.internal"
kubectl get service oracle-host -n "$NAMESPACE" \
  -o jsonpath='{.spec.type}{" -> "}{.spec.externalName}{"\n"}'

echo
echo "==> Restarting the app so we test from a fresh pod"
kubectl rollout restart "deployment/$DEPLOYMENT" -n "$NAMESPACE"
kubectl rollout status "deployment/$DEPLOYMENT" -n "$NAMESPACE"

POD_NAME="$(kubectl get pods -n "$NAMESPACE" -l app=python-vault-app -o jsonpath='{.items[0].metadata.name}')"

echo
echo "==> Confirming oracle-host resolves from inside the app pod"
kubectl exec -n "$NAMESPACE" "$POD_NAME" -c app -- \
  python -c 'import socket; print(socket.getaddrinfo("oracle-host", 1521))'

echo
echo "==> Inspecting the Vault-injected oracle.json in the pod"
kubectl exec -n "$NAMESPACE" "$POD_NAME" -c app -- \
  python -c 'from pathlib import Path; print(Path("/vault/secrets/oracle.json").read_text())'

echo
echo "==> Checking the app-reported config source"
kubectl exec -n "$NAMESPACE" "$POD_NAME" -c app -- \
  python -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8000/config-source").read().decode())'

echo
echo "==> Checking database connectivity through the app"
kubectl exec -n "$NAMESPACE" "$POD_NAME" -c app -- \
  python -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8000/database/connection").read().decode())'

echo
echo "Fix applied. If connectivity still fails, the next thing to inspect is the JDBC URL or credentials stored in Vault."
