"""
Quiet Adoption Demo — execution-gate + OTel + execution-observability-profile

Sends 5 requests through Gate:
  - 3 DENY (AMOUNT_EXCEEDS_LIMIT, NO_RULE, POLICY_UNAVAILABLE sim)
  - 2 ALLOW

Each evaluate() call emits an eb.evaluate span with eb.* attributes.
Spans go to: localhost:4317 (otelcol-agent) → gateway → Jaeger

Verify in Jaeger: http://localhost:16686
  Service: execution-gate
  Tags: eb.decision=DENY
"""
import os
import sys
import time

# --- OTel SDK bootstrap (must run before gate import) ---
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry import trace

resource = Resource.create({
    "service.name": "execution-gate",
    "service.version": "0.3.0",
    "deployment.environment": "local-debug",
})

provider = TracerProvider(resource=resource)
exporter = OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True)
provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)

# --- Gate (instrumentation picks up the provider above) ---
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gate.core import Gate
from gate.decision import ActionEnvelope

POLICY_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "policy.yaml")
gate = Gate(policy_path=POLICY_PATH, platform="quiet-adoption-demo")

scenarios = [
    # (label, action_type, resource, parameters)
    ("ALLOW — email within policy",
     "send_email",      "smtp",       {}),
    ("ALLOW — small transfer within limit",
     "transfer_money",  "bank",       {"amount": 500}),
    ("DENY — amount exceeds limit (500 < 50000)",
     "transfer_money",  "bank",       {"amount": 50_000}),
    ("DENY — explicitly blocked action",
     "delete_database", "database",   {}),
    ("DENY — no rule for action",
     "wire_transfer",   "bank",       {"amount": 1_000}),
]

print(f"\n{'='*60}")
print("Execution Boundary — Quiet Adoption Demo")
print(f"Policy: {POLICY_PATH}")
print(f"OTel endpoint: localhost:4317 (agent → gateway → Jaeger)")
print(f"{'='*60}\n")

for label, action_type, resource_name, params in scenarios:
    envelope = ActionEnvelope.build(
        action_type=action_type,
        resource=resource_name,
        parameters=params,
    )
    decision = gate.evaluate(envelope)

    marker = "✓" if decision.result == "ALLOW" else "✗"
    print(f"  {marker} {label}")
    print(f"    result:      {decision.result}")
    print(f"    reason_code: {decision.reason_code}")
    print(f"    envelope_id: {envelope.action_id}")
    print(f"    proof_hash:  {decision.proof_hash[:16]}...")
    print()
    time.sleep(0.1)  # slight spacing for trace readability

# Flush spans before exit
provider.force_flush()
time.sleep(1)

print(f"{'='*60}")
print("Spans exported. Verify in Jaeger:")
print("  http://localhost:16686")
print("  Service: execution-gate")
print("  Tag filter: eb.decision=DENY")
print()
print("Verification checklist:")
print("  [ ] DENY trace 100% present (3 DENY spans)")
print("  [ ] eb.reason_code visible on each span")
print("  [ ] eb.ledger_commit=true on all spans")
print("  [ ] Single complete trace per request (no fragments)")
print(f"{'='*60}\n")
