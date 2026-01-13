import os
import json
import random
import shutil
from typing import List, Dict, Callable
from datetime import datetime
from pathlib import Path

from environments.traineebench.schemas.common_config import CommonConfig

CURRENT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))

class ResumeSelectGenerator:
    def __init__(
        self, common_config: CommonConfig,
        requirement: list[str],
        position: str,
        number_of_resumes: int = None,
    ) -> None:
        self.common_config = common_config
        self.position = position
        self.requirement = requirement
        self.number_of_resumes = number_of_resumes if number_of_resumes else float('inf')

        # TODO(yxm): check requirements, it should include four dimensions: education, major, years of work experience, and skills.

        self.copy_resumes()
        self.generate_gt_answers()

    def copy_resumes(self):
        resumes = os.listdir(CURRENT_DIR / "resumes")
        # Limit the number of resumes if specified.
        self.number_of_resumes = min(self.number_of_resumes, len(resumes))
        
        # randmmly select resumes
        self.selected_resumes = random.sample(resumes, self.number_of_resumes)
        os.makedirs(os.path.join(
                    self.common_config.cloud_disk_path,
                    "human_resources/resumes"), exist_ok=True)
        for resume in self.selected_resumes:
            shutil.copy2(
                CURRENT_DIR / "resumes" / resume,
                os.path.join(
                    self.common_config.cloud_disk_path,
                    "human_resources/resumes", resume
                )
            )


    def generate_gt_answers(self):
        self.gt_answers = []

        with open(CURRENT_DIR / "resume_info.json", 'r', encoding='utf-8') as rf:
            all_resume_info = json.load(rf)

        resume_info = {}
        for i in range(len(self.selected_resumes)):
            name = self.selected_resumes[i].split('_')[0]
            resume_info[name] = all_resume_info[name]
        education, major, years_of_exp, skills = self.requirement
        for name, resume in resume_info.items():
            if self.position and self.position != resume['position']:
                continue
            if education:
                # The educational background is above the requirement.
                if education == "Master's" and resume['education'] in ["Bachelor's"]:
                    continue
                if education == "Doctoral" and resume['education'] in ["Bachelor's", "Master's"]:
                    continue
            if major and resume['major'] not in major:
                continue
            if years_of_exp:
                if resume['work_experience'].split()[0] < years_of_exp.split()[0]:
                    continue
            if skills:
                for skill in skills:
                    if skill.lower() not in resume['skills']:
                        continue

            self.gt_answers.append(name)

        print('[Requirement]: ', self.requirement)
        print('[Resume Info]', len(resume_info), resume_info)
        print('[Candidate Resumes]: ', self.gt_answers)

    def add_task(self, task_name: str, deadline: datetime):
        education, major, years_of_exp, skills = self.requirement
        prompt = ""
        if education:
            prompt += f"A {education} degree is required; "
        if major:
            if len(major) == 1:
                prompt += f"applicants must have major exactly equal to '{major[0]}'; "
            else:
                majors_list = ", ".join([f"'{m}'" for m in major[:-1]])
                prompt += f"applicants must have a major exactly equal to one of {majors_list} or '{major[-1]}'; "
        if years_of_exp:
            if years_of_exp[:3] == 'Not':
                prompt += "no restrictions on years of service;"
            else:
                prompt += f"applicants must possess a minimum of {years_of_exp} of work experience; "
        if skills:
            prompt += f"has experience in {', '.join(skills)}; "

        task_description = f"""Our company is looking to hire a new {self.position} to help them improve their development. You need to review the collected resumes, which are located in the `CloudDisk:human_resources/resumes/` folder, and filter out suitable candidates. Applicants must demonstrate a clear interest in the position. Other Requirements: {prompt}
        Finally, once you have identified all qualified candidates, create a file named `suitable_candidates.txt` and list their names in the file, **one name per line**. If no suitable candidates are found, create an empty file named `suitable_candidates.txt`."""

        self.common_config.config['tasks'].append(
        {
            # ===== fully observe version prompt =====

            # ===== partially observe version prompt =====
            "task_description": task_description,
            "deadline": deadline,
            "task_name": task_name,
            "evaluation": {
                "name": "resume_selection",
                "args": {
                    "output_file": "suitable_candidates.txt",
                    "gt_answer": self.gt_answers,
                }
            }
        }
    )