# examples/simple_agent.py

from gate import Gate, enforce, BlockedByGate

gate = Gate(policy_path="policy.yaml")

@enforce(gate, intent_builder=lambda amount: {
    "action": "transfer_money",
    "metadata": {"amount": amount}
})
def transfer_money(amount):
    print(f"Transferred {amount}")

if __name__ == "__main__":
    print("=== ALLOW case ===")
    transfer_money(500)

    print("\n=== BLOCK case ===")
    try:
        transfer_money(5000)
    except BlockedByGate as e:
        print("Blocked:", e)
