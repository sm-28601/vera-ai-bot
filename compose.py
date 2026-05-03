"""Core compose() function — hybrid LLM message composition engine."""
from __future__ import annotations
import json
import os
from typing import Optional

# Import your LLM client. Using google-generativeai as an example.
import google.generativeai as genai
from voice_profiles import get_voice, format_salutation, check_taboos

# Ensure your API key is in your environment variables
# (Automatically picking up the key you used in judge_simulator)
api_key = os.environ.get("GEMINI_API_KEY", "AIzaSyAMWCDHU0hQ9ySgSv9a83kw6Rz66KpIuvg")
genai.configure(api_key=api_key)

def compose(category: dict, merchant: dict, trigger: dict, customer: Optional[dict] = None) -> dict:
    # 1. Extract Core Routing Variables (Kept from your original logic)
    kind = trigger.get("kind", "")
    cat_slug = category.get("slug", merchant.get("category_slug", ""))
    owner = merchant.get("identity", {}).get("owner_first_name", "")
    m_name = merchant.get("identity", {}).get("name", "")
    sal = format_salutation(cat_slug, merchant)
    is_customer = trigger.get("scope") == "customer" and customer is not None
    send_as = "merchant_on_behalf" if is_customer else "vera"
    sup_key = trigger.get("suppression_key", f"{kind}:{merchant.get('merchant_id','')}")
    conv_id = f"conv_{merchant.get('merchant_id','')}_{trigger.get('id','')}"

    # 2. Build the System Prompt (The Rules)
    system_prompt = f"""
    You are Vera, an AI assistant for merchant growth. Write a highly compelling, specific, single-message outreach.
    
    VOICE & TONE GUIDELINES:
    Category: {cat_slug}
    Salutation to use: {sal}
    
    STRICT CONSTRAINTS:
    1. SPECIFICITY: Use exact numbers, dates, percentages, or active offers provided in the data. Do not invent metrics.
    2. COMPULSION: End with a single, low-friction yes/no question or easy CTA.
    3. JSON OUTPUT ONLY. You must return pure JSON in this exact format:
    {{
      "body": "The text message to send to the merchant",
      "cta": "The expected action (e.g., 'binary_yes_no' or 'open_ended')",
      "rationale": "One sentence explaining why you wrote this message based on the trigger"
    }}
    """

    # 3. Build the User Prompt (The Dynamic Context)
    # We dump the raw dictionaries so the LLM can extract what it needs
    user_prompt = f"""
    MERCHANT PERFORMANCE & OFFERS: {json.dumps(merchant.get('performance', {}))} | {json.dumps(merchant.get('offers', []))}
    CURRENT TRIGGER: {json.dumps(trigger)}
    CUSTOMER DATA: {json.dumps(customer) if customer else 'None'}
    """

    # 4. Call the LLM with Temperature 0.0 for Determinism
    # Using Gemini 1.5 Flash for speed, forcing JSON output
    model = genai.GenerativeModel(
        'gemini-1.5-flash', 
        generation_config={"temperature": 0.0, "response_mime_type": "application/json"}
    )
    
    try:
        response = model.generate_content(system_prompt + "\n\n" + user_prompt)
        result = json.loads(response.text)
        
        body = result.get("body", "")
        cta = result.get("cta", "open_ended")
        rationale = result.get("rationale", "Generated via LLM")
        
        # Apply your taboo filter to the LLM's output just in case
        taboo_violations = check_taboos(cat_slug, body)
        for t in taboo_violations:
            body = body.replace(t, "")
            
    except Exception as e:
        # Graceful fallback if the network drops or JSON parsing fails
        body = f"{sal}, I noticed an important update regarding your business. Want me to share details?"
        cta = "open_ended"
        rationale = f"LLM generation failed: {str(e)}"

    # 5. Return the exact dictionary shape your bot.py expects
    tpl_params = [owner or m_name, body[:80], ""]
    return {
        "conversation_id": conv_id, 
        "merchant_id": merchant.get("merchant_id"),
        "customer_id": trigger.get("customer_id"), 
        "send_as": send_as,
        "trigger_id": trigger.get("id", ""), 
        "template_name": f"vera_{kind}_v1",
        "template_params": tpl_params, 
        "body": body, 
        "cta": cta,
        "suppression_key": sup_key, 
        "rationale": rationale,
    }
