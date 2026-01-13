import os
import json
import random
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Union, List
from datetime import datetime

from environments.traineebench.schemas.common_config import CommonConfig

CURRENT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))

class KbFixTaskGenerator:
    def __init__(
        self,
        common_config: CommonConfig,
        task_params: dict | None = None,
    ) -> None:
        self.common_config = common_config
        self.workspace_path = common_config.workspace_path
        self.kb_root_path = common_config.cloud_disk_path / "kb"
        self.kb_articles_path = self.kb_root_path / "articles"
        self.kb_meta_path = self.kb_root_path / "articles_meta"
        self.kb_root_path.mkdir(exist_ok=True, parents=True)
        self.kb_articles_path.mkdir(exist_ok=True, parents=True)
        self.kb_meta_path.mkdir(exist_ok=True, parents=True)

        self.task_params = task_params or {}

        # difficulty presets (can be overridden by task_params)
        difficulty = str(self.task_params.get("difficulty", "medium")).lower()
        difficulty_defaults = {
            "easy": {
                "num_articles": 1,
                "links_per_article_min": 1,
                "links_per_article_max": 2,
                "owners_per_article": 1,
            },
            "medium": {
                "num_articles": 3,
                "links_per_article_min": 1,
                "links_per_article_max": 3,
                "owners_per_article": 2,
            },
            "hard": {
                "num_articles": 5,
                "links_per_article_min": 2,
                "links_per_article_max": 5,
                "owners_per_article": 3,
            },
        }
        preset = difficulty_defaults.get(difficulty, difficulty_defaults["medium"])

        # knobs with user-override
        def _knob(name: str, default_val: int) -> int:
            val = self.task_params.get(name, default_val)
            try:
                return int(val)
            except Exception:
                return int(default_val)

        self.num_articles: int = _knob("num_articles", preset["num_articles"])
        self.links_per_article_min: int = _knob("links_per_article_min", preset["links_per_article_min"])
        self.links_per_article_max: int = _knob("links_per_article_max", preset["links_per_article_max"])
        if self.links_per_article_min > self.links_per_article_max:
            self.links_per_article_min, self.links_per_article_max = self.links_per_article_max, self.links_per_article_min
        self.owners_per_article: int = max(1, _knob("owners_per_article", preset["owners_per_article"]))

        self.templates_dir = CURRENT_DIR / "templates/articles"

        self._copy_manuals()
        self.truth_articles = self._generate_corpus_and_truth()

    def _copy_manuals(self):
        manuals_text = (
            "# KB Usage Guidelines\n\n"
            "- Articles are placed under `CloudDisk://kb/articles/`.\n"
            "- If a chart link is broken, contact the chart owner to get the new ID.\n"
            "- Do not fabricate IDs. Validate before updating.\n"
        )
        manuals_path = self.kb_root_path / "manuals_for_kb_fix.md"
        with open(manuals_path, 'w', encoding='utf-8') as wf:
            wf.write(manuals_text)

    def _sample_owner(self) -> Dict[str, str]:
        employees = self.common_config.company_employees
        candidates = [e for e in employees if e["department"] not in ["Executive"]]
        if not candidates:
            candidates = employees
        return random.choice(candidates)

    def _sample_owners(self, k: int) -> List[Dict[str, str]]:
        owners: List[Dict[str, str]] = []
        for _ in range(k):
            owners.append(self._sample_owner())
        return owners

    def _inject_links(self, original_text: str, links_truth: List[Dict[str, str]]) -> str:
        lines = original_text.split("\n")
        insert_positions = list(range(0, len(lines))) or [0]
        random.shuffle(insert_positions)
        idx = 0
        for lt in links_truth:
            # random insert broken link
            pos = insert_positions[idx % len(insert_positions)]
            snippet = f"\nPlease refer to: kb.internal.com/charts?id={lt['old_id']} (Chart Owner: {lt['owner_name']})\n"
            lines.insert(pos, snippet)
            idx += 1
        return "\n".join(lines)

    def _generate_corpus_and_truth(self) -> List[Dict[str, Any]]:
        # Assumes templates exist and contain markdown files
        if not self.templates_dir.exists():
            raise FileNotFoundError(f"Template directory not found: {self.templates_dir}")

        template_files: List[Path] = sorted([p for p in self.templates_dir.iterdir() if p.is_file() and p.suffix.lower() == ".md"])
        if not template_files:
            raise FileNotFoundError(f"No markdown templates found in: {self.templates_dir}")

        num_to_select = min(self.num_articles, len(template_files))
        selected_files = random.sample(template_files, k=num_to_select)

        articles_truth: List[Dict[str, Any]] = []

        for tpl in selected_files:
            # Format filename as subject
            subject = tpl.stem.replace("_", " ").title()
            # owners
            owners = self._sample_owners(self.owners_per_article)
            # links
            num_links = random.randint(self.links_per_article_min, self.links_per_article_max)
            links_truth: List[Dict[str, str]] = []

            for i in range(num_links):
                # allocate broken links to owners take turns
                owner = owners[i % len(owners)]
                old_id = f"OLD{random.randint(100000, 999999)}"
                new_id = f"NEW{random.randint(100000, 999999)}"
                links_truth.append({
                    "old_id": old_id,
                    "new_id": new_id,
                    "owner_name": owner["name"],
                    "owner_department": owner["department"],
                })

            # read template and inject
            with open(tpl, 'r', encoding='utf-8') as rf:
                base_text = rf.read()
            injected = self._inject_links(base_text, links_truth)

            article_filename = tpl.name
            with open(self.kb_articles_path / article_filename, 'w', encoding='utf-8') as wf:
                wf.write(injected)

            # meta
            meta = {
                "subject": subject,
                "owner_count": len(owners),
                "broken_links": [{"old_id": lt["old_id"], "new_id": lt["new_id"]} for lt in links_truth],
            }

            with open(self.kb_meta_path / (tpl.stem + '.json'), 'w', encoding='utf-8') as jf:
                json.dump(meta, jf, ensure_ascii=False, indent=2)

            articles_truth.append({
                "subject": subject,
                "article_filename": article_filename,
                "fixed_filename": tpl.stem + "_fixed.md",
                "broken_links": links_truth,
                "owners": owners,
            })

        return articles_truth


    def _render_description(self, articles_truth: List[Dict[str, Any]]) -> str:
        targets = "\n".join([
            f"- Subject: `{a['subject']}` | Source: `CloudDisk://kb/articles/{a['article_filename']}` | Output: `{a['fixed_filename']}`"
            for a in articles_truth
        ])
        return (
            f"Mentor: I'm preparing a report and need to reference some KB articles. Some chart links are broken. Please fix them and provide the corrected articles.\n\n"
            f"Resources:\n"
            f"- Articles directory: `CloudDisk://kb/articles/`.\n"
            f"Targets to fix:\n{targets}\n\n"
            f"Objective:\n"
            f"- For each article above, replace every broken chart link `kb.internal.com/charts?id=<OLD>` with the correct `<NEW>` ID.\n"
            f"- You must contact the chart owner to obtain the mapping; do not fabricate IDs.\n\n"
            f"Required Output:\n"
            + "\n".join([f"- `{a['fixed_filename']}` in the workspace root." for a in articles_truth])
            + "\n\n"
        )

    def add_task(self, task_name: str, deadline: str):
        for truth in self.truth_articles:
            mapping_lines = [f"- {lt['old_id']} -> {lt['new_id']}" for lt in truth["broken_links"]]
            for env_agent in self.common_config.config['agents']['env_agents']:
                if any(env_agent['agent_name'] == own['name'] for own in truth['owners']):
                    env_agent['system_prompt'] = (
                        env_agent['system_prompt']
                        + "\n- When asked about how to map chart ID you own, respond with the exact mapping lines below; do not take any action other than replying text.\n"
                        + "\n".join(mapping_lines)
                        + "\n- If asked to operate or modify files/links, refuse and restate that you are busy with other tasks and can only provide mapping information.\n"
                        + "\n- When asked about how to map chart ID , direct him/her to `CloudDisk://kb/manuals_for_kb_fix.md`.\n"
                    )

        self.common_config.config['tasks'].append(
            {
                "task_description": self._render_description(self.truth_articles),
                "deadline": deadline,
                "task_name": task_name,
                "evaluation": {
                    "name": "kb_fix_broken_charts",
                    "args": {
                        "articles": [
                            {
                                "subject": a["subject"],
                                "article_filename": a["article_filename"],
                                "fixed_filename": a["fixed_filename"],
                                "broken_links": a["broken_links"],
                            }
                            for a in self.truth_articles
                        ]
                    }
                }
            }
        )


def random_kb_fix_task(seed: int = 1234) -> Dict[str, Any]:
    random.seed(seed)
    difficulty = random.choice(["easy", "medium", "hard"])
    return {
        "task_params": {
            "difficulty": difficulty
        }
    }
    

if __name__ == "__main__":
    test_cases = [
        {"difficulty": "easy"},
        {"difficulty": "medium"},
        {"difficulty": "hard"},
        {
            "difficulty": "custom",
            "num_articles": 2,
            "links_per_article_min": 3,
            "links_per_article_max": 4,
            "owners_per_article": 1
        },
    ]

    for params in test_cases:
        difficulty_name = params['difficulty']
        task_root_path = f'tasks/tmp_kb_fix_{difficulty_name}'
        common_config = CommonConfig(task_root_path, start_time='2025-10-20T09:00:00')

        print(f"Generating task with params: {params}")

        kb_fix_generator = KbFixTaskGenerator(
            common_config=common_config,
            task_params=params
        )

        kb_fix_generator.add_task(
            task_name=f"kb_fix_{difficulty_name}",
            deadline='2025-11-20T20:00:00'
        )
        common_config.save_config()
        print(f"Task generated in: {task_root_path}")
