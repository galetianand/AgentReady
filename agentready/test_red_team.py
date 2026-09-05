from schemas.mandate import BuyerIntentMandate
from core.policy_engine import DeterministicPolicyEngine

def test_budget_overflow_block():
    """Verify: Transactions exceeding user budget mandate are strictly rejected."""
    mandate = BuyerIntentMandate(
        mandate_id="mnd_attack_budget",
        user_id="usr_01",
        category="PERIPHERALS_KEYBOARDS",
        max_budget_inr=25000.0,
        target_quantity=10
    )
    # Attempted malicious price: ₹3,500/unit = ₹35,000 total (₹10,000 over budget)
    is_valid, reason = DeterministicPolicyEngine.validate_transaction(
        mandate=mandate,
        merchant_id="mer_techgear_01",
        agreed_unit_price=3500.0,
        quantity=10
    )
    assert not is_valid, "Failed: Policy Engine allowed budget breach"
    print(f" [PASSED] Budget Overflow Blocked: {reason}")

def test_quantity_tamper_block():
    """Verify: Unauthorized quantity modification is intercepted."""
    mandate = BuyerIntentMandate(
        mandate_id="mnd_attack_qty",
        user_id="usr_01",
        category="PERIPHERALS_KEYBOARDS",
        max_budget_inr=25000.0,
        target_quantity=10
    )
    # Injected quantity: 15 instead of authorized 10
    is_valid, reason = DeterministicPolicyEngine.validate_transaction(
        mandate=mandate,
        merchant_id="mer_techgear_01",
        agreed_unit_price=2400.0,
        quantity=15
    )
    assert not is_valid, "Failed: Policy Engine allowed quantity tamper"
    print(f" [PASSED] Quantity Tamper Blocked: {reason}")

def test_idempotency_hash_consistency():
    """Verify: Identical mandate parameters produce deterministic SHA-256 keys."""
    k1 = DeterministicPolicyEngine.generate_idempotency_key("mnd_001", "mer_01", "qt_token_123")
    k2 = DeterministicPolicyEngine.generate_idempotency_key("mnd_001", "mer_01", "qt_token_123")
    assert k1 == k2, "Failed: Idempotency keys do not match"
    print(f" [PASSED] Deterministic Idempotency Key Verified: {k1[:16]}...")

if __name__ == "__main__":
    print("\n--- RUNNING AGENTREADY RED TEAM TEST HARNESS ---")
    test_budget_overflow_block()
    test_quantity_tamper_block()
    test_idempotency_hash_consistency()
    print("--- ALL 3 CORE GUARDRAIL TESTS PASSED ---\n")