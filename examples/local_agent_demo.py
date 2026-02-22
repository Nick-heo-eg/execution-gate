from gate import Gate, enforce, BlockedByGate


gate = Gate(
    policy_path="./policy.yaml",
    platform="local-demo",
    model="local-llm",
    audit_file=None,  # stdout
)

def transfer_intent_builder(amount: float):
    return {"actor": "agent", "action": "transfer_money", "metadata": {"amount": amount}}

@enforce(gate, intent_builder=lambda amount: transfer_intent_builder(amount))
def transfer_money(amount: float):
    return f"✅ transferred: {amount}"

@enforce(gate, intent_builder=lambda: {"actor": "agent", "action": "delete_database", "metadata": {}})
def delete_database():
    return "💥 deleted"

if __name__ == "__main__":
    try:
        print(transfer_money(500))
        print(transfer_money(5000))   # should BLOCK
    except BlockedByGate as e:
        print("BLOCKED:", e.reason_code, e.decision_reason)

    try:
        print(delete_database())       # should BLOCK
    except BlockedByGate as e:
        print("BLOCKED:", e.reason_code, e.decision_reason)
