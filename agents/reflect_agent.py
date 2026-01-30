import json
import re
import openai
import httpx
from typing import Tuple, List, Dict, Union, Any


def get_config(model: str):
    with open('api_config.json', 'r', encoding='utf-8') as rf:
        api_configs: Dict[str, Dict] = json.load(rf)

    model_name = api_configs[model]['model_name']
    api_key = api_configs[model]['api_key_var']
    base_url = api_configs[model]['base_url']
    proxy_url = api_configs[model].get('proxy_url', None)

    return model_name, api_key, base_url, proxy_url

with open('agents/prompts/reflection.txt', 'r', encoding='utf-8') as rf:
    REFLECTION_PROMPT = rf.read()

class ReflectAgent:
    def __init__(self, model_name: str):
        model_name, api_key, base_url, proxy_url = get_config(model_name)
        
        # 初始化 Client
        if proxy_url:
            self.client = openai.OpenAI(
                api_key=api_key,
                base_url=base_url,
                http_client=httpx.Client(proxy=proxy_url)
            )
        else:
            self.client = openai.OpenAI(
                api_key=api_key,
                base_url=base_url
            )
        self.model_name = model_name

        self.messages: List[Dict] = [
            {
                "role": "system",
                "content": REFLECTION_PROMPT
            }
        ]

    def _extract_json_str(self, text: str) -> str:
        """
        Extract JSON list string from text, handling markdown code blocks.
        Looks for [...] pattern.
        """
        text = text.strip()
        
        pattern = r"(?i)```json\s*($$.*?$$)\s*```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1)

        pattern_generic = r"```\s*($$.*?$$)\s*```"
        match_generic = re.search(pattern_generic, text, re.DOTALL)
        if match_generic:
            return match_generic.group(1)

        start = text.find('[')
        end = text.rfind(']')
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1]
            
        return text

    def _validate_response(self, content: str) -> Tuple[bool, Union[List[Dict], str]]:
        json_str = self._extract_json_str(content)

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            if not json_str:
                 return False, "Error: No JSON content found."
            return False, "Error: The output is not valid JSON. Please ensure standard JSON formatting."

        if not isinstance(data, list):
            return False, "Error: The Output JSON must be a List (Array) `[...]`, not a Dictionary."

        for index, item in enumerate(data):
            if not isinstance(item, dict):
                return False, f"Error: Item at index {index} is not a valid object."
            
            if "scenario" not in item:
                return False, f"Error: Item at index {index} is missing the 'scenario' field."
                
            if "solution" not in item:
                return False, f"Error: Item at index {index} is missing the 'solution' field."
            
            if not isinstance(item["scenario"], str) or not item["scenario"].strip():
                 return False, f"Error: 'scenario' at index {index} must be a non-empty string."

        return True, data

    def response(
            self, 
            prompt: str = '', 
            temperature: float = 0.8, 
            top_p: float = 1.0,
            max_retries: int = 3
        ) -> List[Dict]:
        
        self.messages.append({"role": "user", "content": prompt})

        current_retries = 0

        while current_retries < max_retries:
            try:
                res = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=self.messages,
                    temperature=temperature,
                    top_p=top_p
                )
                res_content = res.choices[0].message.content
                
                self.messages.append({"role": "assistant", "content": res_content})

                is_valid, result = self._validate_response(res_content)

                if is_valid:
                    return result
                else:
                    error_msg = result
                    print(f"ReflectAgent Warning: Validation failed ({error_msg}). Retrying {current_retries + 1}/{max_retries}...")
                    
                    # Instruction for the model to fix the format
                    correction_prompt = (
                        f"Your previous response had the following format error: {error_msg}\n"
                        "Please reformulate your response strictly as a JSON List: "
                        "[{\"scenario\": \"...\", \"solution\": \"...\"}, ...]"
                    )
                    
                    self.messages.append({"role": "user", "content": correction_prompt})
                    current_retries += 1
            
            except Exception as e:
                print(f"ReflectAgent API Error: {e}")
                current_retries += 1

        print("ReflectAgent failed to generate valid JSON after max retries. Returning empty list.")
        return []
