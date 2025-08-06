import os
import json
import requests
from typing import Dict, List

class TextAnalysis:
    def __init__(self, text: str, thread_context: List[str] = []):
        self.text = text
        self.thread_context = thread_context
        self.api_key = os.getenv('GEMINI_API_KEY')

    def analyse(self, db_connection=None, save_to_db: bool = True) -> Dict:
        """
        Analyze the text for inappropriate content using the Gemini API,
        considering the context of the conversation thread.
        """
        if not self.api_key:
            return {
                "decision": "error",
                "reason": "API_KEY_NOT_FOUND",
                "details": "GEMINI_API_KEY is not set in the environment."
            }

        prompt = self._build_prompt()
        
        try:
            response = self._call_gemini_api(prompt)
            moderation_result = self._parse_gemini_response(response)

            # Save to database regardless of decision (per user requirements)
            if save_to_db and db_connection:
                db_connection.save_flagged_text(
                    text=self.text,
                    decision=moderation_result.get("decision", "error"),
                    reason=moderation_result.get("reason", "No reason provided"),
                    raw_response=response
                )
            
            return moderation_result

        except requests.exceptions.RequestException as e:
            return {"decision": "error", "reason": "API_REQUEST_FAILED", "details": str(e)}
        except (ValueError, KeyError) as e:
            return {"decision": "error", "reason": "RESPONSE_PARSING_FAILED", "details": str(e)}

    def _build_prompt(self) -> str:
        """
        Build the prompt for the Gemini API, including the conversation context.
        """
        context_str = "\n".join(f"- {msg}" for msg in self.thread_context)
        
        return f"""You are a content moderator for a social media platform. You must analyze messages for community standard violations.

CRITICAL: You MUST respond with ONLY a valid JSON object. No markdown, no explanations, no additional text.

COMMUNITY STANDARDS - Flag content that contains:
- Hate speech (attacks on race, religion, ethnicity, nationality, sexual orientation, gender identity)
- Harassment or personal attacks (insults, name-calling, bullying)
- Threats of violence (direct or implied threats of harm)
- Explicit sexual content (graphic sexual descriptions, solicitation)
- Spam or commercial solicitation
- Doxxing or sharing private information

CONVERSATION CONTEXT:
{context_str}

MESSAGE TO ANALYZE:
"{self.text}"

DECISION RULES:
- "pass": Content is appropriate and follows community standards
- "review": Content is borderline and needs human review (mild profanity, heated debate, unclear intent)
- "flagged": Content clearly violates community standards

REQUIRED OUTPUT FORMAT:
You must respond with EXACTLY this JSON structure (no other text):

{{
  "decision": "pass|review|flagged",
  "reason": "Brief explanation in one sentence"
}}

EXAMPLES:
For harassment: {{"decision": "flagged", "reason": "Contains personal attacks and insults directed at another user"}}
For debate: {{"decision": "pass", "reason": "Expresses disagreement respectfully without personal attacks"}}
For borderline: {{"decision": "review", "reason": "Contains strong language that may require human judgment"}}

Analyze the message and respond with ONLY the JSON object:"""

    def _call_gemini_api(self, prompt: str) -> Dict:
        """
        Call the Gemini API with the specified prompt.
        """
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"
        headers = {'Content-Type': 'application/json'}
        data = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }]
        }
        
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()

    def _parse_gemini_response(self, response: Dict) -> Dict:
        """
        Parse the JSON response from the Gemini API with robust error handling.
        """
        try:
            # Extract the text content which should be a JSON string
            content_text = response['candidates'][0]['content']['parts'][0]['text']
            
            # Clean up the response to ensure it's valid JSON
            clean_json_str = content_text.strip()
            
            # Remove markdown code blocks if present
            if clean_json_str.startswith("```json"):
                clean_json_str = clean_json_str[7:]
            elif clean_json_str.startswith("```"):
                clean_json_str = clean_json_str[3:]
            if clean_json_str.endswith("```"):
                clean_json_str = clean_json_str[:-3]
            
            clean_json_str = clean_json_str.strip()
            
            # Remove any leading/trailing text that isn't JSON
            start_idx = clean_json_str.find('{')
            end_idx = clean_json_str.rfind('}')
            
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                clean_json_str = clean_json_str[start_idx:end_idx + 1]
            else:
                raise ValueError("No valid JSON object found in response")
            
            # Parse the JSON string into a Python dictionary
            moderation_data = json.loads(clean_json_str)
            
            # Validate the parsed data structure
            if not isinstance(moderation_data, dict):
                raise ValueError("Response is not a JSON object")
                
            if "decision" not in moderation_data:
                raise ValueError("Missing 'decision' field in response")
                
            if "reason" not in moderation_data:
                raise ValueError("Missing 'reason' field in response")
            
            # Validate decision values
            valid_decisions = ["pass", "review", "flagged"]
            if moderation_data["decision"] not in valid_decisions:
                # If invalid decision, default to review for safety
                moderation_data["decision"] = "review"
                moderation_data["reason"] = f"Invalid decision format: {moderation_data['decision']}"
            
            # Ensure reason is a string
            if not isinstance(moderation_data["reason"], str):
                moderation_data["reason"] = str(moderation_data["reason"])
            
            return moderation_data
            
        except (json.JSONDecodeError, KeyError, IndexError, ValueError) as e:
            # If parsing fails completely, return a safe default response
            return {
                "decision": "review",
                "reason": f"AI response parsing failed - flagged for manual review (Error: {str(e)})"
            }
