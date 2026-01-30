import re
import json
from typing import List, Dict, Any

class ContentEditor:
    def __init__(self, init_tag: str, edit_tag: str):
        self.content: List[str] = []
        self.init_regex = re.compile(
            f'<{re.escape(init_tag)}>(.*?)</{re.escape(init_tag)}>', re.DOTALL
            )
        self.edit_regex = re.compile(
            f'<{re.escape(edit_tag)}>(.*?)</{re.escape(edit_tag)}>', re.DOTALL
            )

    def process_response(self, model_response: str) -> bool:
        init_match = self.init_regex.search(model_response)
        edit_match = self.edit_regex.search(model_response)

        if init_match:
            list_content = init_match.group(1).strip()
            self._initialize_from_list(list_content)
            return True
        elif edit_match:
            updates_content = edit_match.group(1).strip()
            self._apply_updates(updates_content)
            return True
        else:
            return False

    def _initialize_from_list(self, list_str: str):
        self.content = list_str.split('\n')

    def _apply_updates(self, updates_str: str):
        lines = updates_str.strip().split('\n')
        operations: List[Dict[str, Any]] = []
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue

            try:
                if line.startswith('REPLACE '):
                    parts = line.split(maxsplit=1)
                    line_num = int(parts[1])
                    # Collect all content lines of REPLACE
                    content_lines = []
                    i += 1
                    while i < len(lines) and not (lines[i].lstrip().startswith('REPLACE ') or \
                                                  lines[i].lstrip().startswith('INSERT-AFTER ') or \
                                                  lines[i].lstrip().startswith('DELETE ')):
                        content_lines.append(lines[i]) # Preserve original indentation
                        i += 1
                    operations.append({'op': 'REPLACE', 'line': line_num - 1, 'content': content_lines})
                
                elif line.startswith('INSERT-AFTER '):
                    # pattern: INSERT-AFTER <line_number>: <new_content>
                    _, rest = line.split(maxsplit=1)
                    line_num_str, new_content = rest.split(':', 1)
                    line_num = int(line_num_str)
                    operations.append({'op': 'INSERT-AFTER', 'line': line_num - 1, 'content': new_content.lstrip()})
                    i += 1
                
                elif line.startswith('DELETE '):
                    parts = line.split(maxsplit=1)
                    line_num = int(parts[1])
                    operations.append({'op': 'DELETE', 'line': line_num - 1})
                    i += 1
                else:
                    i += 1
            except (ValueError, IndexError) as e:
                i += 1
        
        # 2. Sort by row number in descending order
        operations.sort(key=lambda x: x['line'], reverse=True)
        
        # 3. Perform sorted operations
        for op in operations:
            line_num = op['line']
            
            # Check if the line number is valid.
            if not (0 <= line_num < len(self.content)):
                continue

            if op['op'] == 'REPLACE':
                # Replace the old single line with the new multi-line content.
                self.content[line_num : line_num + 1] = op['content']
            elif op['op'] == 'INSERT-AFTER':
                self.content.insert(line_num + 1, op['content'])
            elif op['op'] == 'DELETE':
                self.content.pop(line_num)

    def view_content(self) -> str:
        if not self.content:
            return ""

        max_line_num_width = len(str(len(self.content)))

        formatted_list = [
            f"{i + 1:>{max_line_num_width}} |{line}"
            for i, line in enumerate(self.content)
        ]

        return "\n".join(formatted_list)