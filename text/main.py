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
        
        return f"""
        You are a content moderator for a social media platform. Your task is to analyze a new message for any violations of our community standards, based on the context of the preceding conversation.

        **Community Standards:** Do not allow:
        - Hate speech (attacks on race, religion, ethnicity, etc.)
        - Harassment or personal attacks
        - Threats of violence
        - Explicitly sexual content

        **Conversation Thread (for context):**
        {context_str}

        **New Message to Analyze:**
        "{self.text}"

        **Your Analysis:**
        Based on the community standards and the conversation context, analyze the new message. Respond with a JSON object containing your decision. The JSON object must have two keys:
        1. "decision": A string that is one of "pass", "review", or "flagged".
        2. "reason": A brief, one-sentence explanation for your decision.

        Example Response:
        {{
          "decision": "flagged",
          "reason": "The message contains a personal attack against another user."
        }}

        Provide only the JSON object in your response.
        """

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
        Parse the JSON response from the Gemini API.
        """
        # Extract the text content which should be a JSON string
        content_text = response['candidates'][0]['content']['parts'][0]['text']
        
        # Clean up the response to ensure it's valid JSON
        clean_json_str = content_text.strip().replace("```json", "").replace("```", "").strip()
        
        # Parse the JSON string into a Python dictionary
        moderation_data = json.loads(clean_json_str)
        
        # Validate the parsed data
        if "decision" not in moderation_data or "reason" not in moderation_data:
            raise ValueError("Invalid JSON structure in response")
            
        return moderation_data
