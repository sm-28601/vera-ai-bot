"""Generate submission.jsonl using the composer."""
from __future__ import annotations

import json
from pathlib import Path
from state import ContextStore, ConversationState, SuppressionManager
from decision_engine import select_triggers
from compose import compose

def main():
    base_dir = Path("d:/magicpin/expanded")
    out_file = Path("d:/magicpin/submission.jsonl")

    ctx = ContextStore()

    # Load everything into context store
    print("Loading contexts...")
    for f in (base_dir / "categories").glob("*.json"):
        d = json.loads(f.read_text("utf-8"))
        ctx.push("category", d["slug"], 1, d)

    for f in (base_dir / "merchants").glob("*.json"):
        d = json.loads(f.read_text("utf-8"))
        ctx.push("merchant", d["merchant_id"], 1, d)

    for f in (base_dir / "customers").glob("*.json"):
        d = json.loads(f.read_text("utf-8"))
        ctx.push("customer", d["customer_id"], 1, d)

    for f in (base_dir / "triggers").glob("*.json"):
        d = json.loads(f.read_text("utf-8"))
        ctx.push("trigger", d["id"], 1, d)

    pairs_data = json.loads((base_dir / "test_pairs.json").read_text("utf-8"))
    pairs = pairs_data.get("pairs", [])
    
    print(f"Generating messages for {len(pairs)} test pairs...")
    
    with open(out_file, "w", encoding="utf-8") as f_out:
        for p in pairs:
            tid = p["trigger_id"]
            mid = p["merchant_id"]
            cid = p.get("customer_id")
            test_id = p.get("test_id", "")
            
            trigger = ctx.get("trigger", tid)
            merchant = ctx.get("merchant", mid)
            category = ctx.get("category", merchant.get("category_slug", ""))
            customer = ctx.get("customer", cid) if cid else None
            
            res = compose(category, merchant, trigger, customer)
            res["test_id"] = test_id
            
            f_out.write(json.dumps(res, ensure_ascii=False) + "\n")
            
    print(f"Done! Created {out_file}")

if __name__ == "__main__":
    main()
